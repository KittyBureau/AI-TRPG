from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from backend.domain.fact_models import CampaignFact, CampaignFactCreate
from backend.domain.models import Campaign
from backend.infra.file_repo import FileRepo

_FACT_PROMPT_LIMIT = 5
_FACT_STORAGE_SOFT_LIMIT = 64
_FACT_TEMPORARY_TTL_TURNS = 6
_NPC_MEMORY_PROMPT_LIMIT = 3
_NPC_MEMORY_MAX_SUMMARY_CHARS = 140

_PROMPT_SCOPE_PRIORITY = {
    "entity_selected": 0,
    "npc_selected": 0,
    "item_selected": 0,
    "area_current": 1,
    "campaign": 2,
    "actor_current": 3,
    "area_other": 4,
}

_RELIABILITY_PRUNE_PRIORITY = {
    "generated": 0,
    "reported": 1,
    "confirmed": 2,
}


class CampaignFactService:
    def __init__(self, repo: FileRepo) -> None:
        self.repo = repo

    def add_fact(
        self,
        campaign_id: str,
        payload: CampaignFactCreate | Dict[str, object],
    ) -> CampaignFact:
        campaign = self.repo.get_campaign(campaign_id)
        request = (
            payload
            if isinstance(payload, CampaignFactCreate)
            else CampaignFactCreate.model_validate(payload)
        )
        created_turn_index = self._infer_created_turn_index(
            campaign_id, request.created_turn_index
        )
        fact = add_fact_to_campaign(
            campaign,
            request,
            created_turn_index=created_turn_index,
        )
        prune_campaign_facts(
            campaign,
            current_turn_index=created_turn_index,
            keep_fact_ids={fact.fact_id},
        )
        self.repo.save_campaign(campaign)
        persisted = campaign.facts.get(fact.fact_id)
        return persisted if isinstance(persisted, CampaignFact) else fact

    def get_fact(self, campaign_id: str, fact_id: str) -> Optional[CampaignFact]:
        campaign = self.repo.get_campaign(campaign_id)
        return campaign.facts.get(fact_id)

    def list_facts(
        self,
        campaign_id: str,
        *,
        authority: Optional[str] = None,
        scope_kind: Optional[str] = None,
        scope_ref_id: Optional[str] = None,
    ) -> List[CampaignFact]:
        campaign = self.repo.get_campaign(campaign_id)
        return list(
            _iter_filtered_facts(
                campaign.facts.values(),
                authority=authority,
                scope_kind=scope_kind,
                scope_ref_id=scope_ref_id,
            )
        )

    def _infer_created_turn_index(
        self, campaign_id: str, explicit: Optional[int]
    ) -> int:
        if isinstance(explicit, int):
            return explicit
        next_turn_id = self.repo.next_turn_id(campaign_id)
        return max(0, _turn_id_to_number(next_turn_id) - 1)


def add_fact_to_campaign(
    campaign: Campaign,
    payload: CampaignFactCreate | Dict[str, object],
    *,
    created_turn_index: int,
) -> CampaignFact:
    request = (
        payload
        if isinstance(payload, CampaignFactCreate)
        else CampaignFactCreate.model_validate(payload)
    )
    fact = _build_fact_from_request(
        campaign,
        request,
        created_turn_index=created_turn_index,
    )
    duplicate = _find_exact_duplicate(campaign.facts.values(), fact)
    if duplicate is not None:
        return duplicate
    if fact.fact_id in campaign.facts:
        raise ValueError(f"fact_id already exists: {fact.fact_id}")
    campaign.facts[fact.fact_id] = fact
    return fact


def build_fact_prompt_context(
    campaign: Campaign,
    effective_actor_id: str,
    *,
    current_turn_index: Optional[int] = None,
    max_items: int = _FACT_PROMPT_LIMIT,
    selected_item_id: Optional[str] = None,
    selected_scene_target_id: Optional[str] = None,
) -> Dict[str, object]:
    selection = _select_facts_for_prompt(
        campaign,
        effective_actor_id,
        current_turn_index=current_turn_index,
        max_items=max_items,
        selected_item_id=selected_item_id,
        selected_scene_target_id=selected_scene_target_id,
    )
    return {
        "slot": "campaign_facts_v1",
        "authoritative": list(selection["authoritative"]),
        "uncertain": list(selection["uncertain"]),
    }


def build_npc_memory_context(
    campaign: Campaign,
    *,
    npc_id: Optional[str],
    npc_label: Optional[str] = None,
    current_turn_index: Optional[int] = None,
    max_items: int = _NPC_MEMORY_PROMPT_LIMIT,
) -> Optional[Dict[str, object]]:
    if not isinstance(npc_id, str) or not npc_id.strip():
        return None
    selection = _select_npc_memory_facts(
        campaign,
        npc_id=npc_id.strip(),
        current_turn_index=current_turn_index,
        max_items=max_items,
    )
    payload: Dict[str, object] = {
        "slot": "npc_memory_v1",
        "npc_id": npc_id.strip(),
        "items": list(selection["items"]),
    }
    if isinstance(npc_label, str) and npc_label.strip():
        payload["npc_label"] = npc_label.strip()
    if selection["fact_ids"]:
        payload["fact_ids"] = list(selection["fact_ids"])
    return payload


def build_npc_memory_debug_context(
    campaign: Campaign,
    *,
    npc_id: Optional[str],
    npc_label: Optional[str] = None,
    current_turn_index: Optional[int] = None,
    max_items: int = _NPC_MEMORY_PROMPT_LIMIT,
) -> Optional[Dict[str, object]]:
    if not isinstance(npc_id, str) or not npc_id.strip():
        return None
    selection = _select_npc_memory_facts(
        campaign,
        npc_id=npc_id.strip(),
        current_turn_index=current_turn_index,
        max_items=max_items,
    )
    payload: Dict[str, object] = {
        "slot": "npc_memory_v1",
        "npc_id": npc_id.strip(),
        "items": list(selection["items"]),
        "fact_ids": list(selection["fact_ids"]),
        "expired_fact_ids": list(selection["expired_fact_ids"]),
        "omitted_due_to_limit_ids": list(selection["omitted_due_to_limit_ids"]),
        "selected_count": len(selection["items"]),
        "max_items": max_items,
    }
    if isinstance(npc_label, str) and npc_label.strip():
        payload["npc_label"] = npc_label.strip()
    return payload


def record_npc_memory_fact(
    campaign: Campaign,
    *,
    actor_id: str,
    npc_id: str,
    npc_label: str,
    user_input: str,
    turn_id: str,
    current_turn_index: int,
) -> Optional[CampaignFact]:
    summary = _build_npc_memory_summary(user_input)
    if summary is None:
        return None
    return add_fact_to_campaign(
        campaign,
        CampaignFactCreate(
            fact_type="npc_memory",
            summary=summary,
            source={
                "kind": "system",
                "ref_id": turn_id,
                "actor_id": actor_id,
            },
            authority="uncertain",
            reliability="generated",
            scope={"kind": "npc", "ref_id": npc_id},
            lifecycle="temporary",
            metadata={"npc_label": npc_label.strip()} if npc_label.strip() else {},
        ),
        created_turn_index=current_turn_index,
    )


def build_fact_debug_context(
    campaign: Campaign,
    effective_actor_id: str,
    *,
    current_turn_index: Optional[int] = None,
    max_items: int = _FACT_PROMPT_LIMIT,
    selected_item_id: Optional[str] = None,
    selected_scene_target_id: Optional[str] = None,
) -> Dict[str, object]:
    selection = _select_facts_for_prompt(
        campaign,
        effective_actor_id,
        current_turn_index=current_turn_index,
        max_items=max_items,
        selected_item_id=selected_item_id,
        selected_scene_target_id=selected_scene_target_id,
    )
    return {
        "slot": "campaign_facts_v1",
        "selection": dict(selection["selection"]),
        "authoritative": list(selection["authoritative"]),
        "uncertain": list(selection["uncertain"]),
        "selected_fact_ids": list(selection["selected_fact_ids"]),
        "expired_temporary_ids": list(selection["expired_temporary_ids"]),
        "suppressed_uncertain_ids": list(selection["suppressed_uncertain_ids"]),
        "omitted_due_to_limit_ids": list(selection["omitted_due_to_limit_ids"]),
        "eligible_count": int(selection["eligible_count"]),
        "policy": {
            "authoritative_precedence": True,
            "same_source_duplicate_strategy": "exact_match_dedupe",
            "automatic_merge": False,
            "max_prompt_facts": max_items,
            "temporary_ttl_turns": _FACT_TEMPORARY_TTL_TURNS,
            "storage_soft_limit": _FACT_STORAGE_SOFT_LIMIT,
        },
    }


def prune_campaign_facts(
    campaign: Campaign,
    *,
    current_turn_index: Optional[int] = None,
    max_total: int = _FACT_STORAGE_SOFT_LIMIT,
    keep_fact_ids: Optional[set[str]] = None,
) -> List[str]:
    resolved_turn_index = _resolve_current_turn_index(
        campaign, current_turn_index=current_turn_index
    )
    protected_ids = keep_fact_ids or set()
    removed_ids: List[str] = []

    for fact in list(campaign.facts.values()):
        if fact.fact_id in protected_ids:
            continue
        if not _is_expired_temporary_fact(fact, current_turn_index=resolved_turn_index):
            continue
        campaign.facts.pop(fact.fact_id, None)
        removed_ids.append(fact.fact_id)

    if max_total < 1:
        return removed_ids
    if len(campaign.facts) <= max_total:
        return removed_ids

    removable = [
        fact
        for fact in campaign.facts.values()
        if fact.fact_id not in protected_ids and fact.lifecycle == "temporary"
    ]
    removable.sort(key=_temporary_prune_rank)
    while len(campaign.facts) > max_total and removable:
        fact = removable.pop(0)
        if campaign.facts.pop(fact.fact_id, None) is not None:
            removed_ids.append(fact.fact_id)

    return removed_ids


def _select_facts_for_prompt(
    campaign: Campaign,
    effective_actor_id: str,
    *,
    current_turn_index: Optional[int],
    max_items: int,
    selected_item_id: Optional[str],
    selected_scene_target_id: Optional[str],
) -> Dict[str, object]:
    actor_state = campaign.actors.get(effective_actor_id)
    active_area_id = (
        actor_state.position
        if actor_state is not None and isinstance(actor_state.position, str)
        else None
    )
    resolved_turn_index = _resolve_current_turn_index(
        campaign, current_turn_index=current_turn_index
    )
    selection = {
        "effective_actor_id": effective_actor_id,
        "active_area_id": active_area_id,
        "selected_item_id": selected_item_id,
        "selected_scene_target_id": selected_scene_target_id,
        "current_turn_index": resolved_turn_index,
        "max_prompt_facts": max(0, max_items),
    }

    expired_temporary_ids: List[str] = []
    candidates: List[CampaignFact] = []
    for fact in _sorted_facts(campaign.facts.values()):
        if _is_expired_temporary_fact(fact, current_turn_index=resolved_turn_index):
            expired_temporary_ids.append(fact.fact_id)
            continue
        if not _fact_is_prompt_eligible(
            fact,
            effective_actor_id=effective_actor_id,
            active_area_id=active_area_id,
            selected_item_id=selected_item_id,
            selected_scene_target_id=selected_scene_target_id,
        ):
            continue
        candidates.append(fact)

    candidates.sort(
        key=lambda fact: _prompt_rank(
            fact,
            effective_actor_id=effective_actor_id,
            active_area_id=active_area_id,
            selected_item_id=selected_item_id,
            selected_scene_target_id=selected_scene_target_id,
        )
    )

    selected: List[CampaignFact] = []
    suppressed_uncertain_ids: List[str] = []
    authoritative_keys: set[tuple[str, str, str]] = set()
    for fact in candidates:
        if fact.authority == "authoritative":
            selected.append(fact)
            authoritative_keys.add(_conflict_key(fact))
            continue
        if _conflict_key(fact) in authoritative_keys:
            suppressed_uncertain_ids.append(fact.fact_id)
            continue
        selected.append(fact)

    limited = selected[: max(0, max_items)]
    selected_ids = [fact.fact_id for fact in limited]
    omitted_due_to_limit_ids = [
        fact.fact_id for fact in selected[max(0, max_items) :]
    ]

    authoritative_payloads: List[Dict[str, object]] = []
    uncertain_payloads: List[Dict[str, object]] = []
    for fact in limited:
        payload = _fact_prompt_payload(fact)
        if fact.authority == "authoritative":
            authoritative_payloads.append(payload)
        else:
            uncertain_payloads.append(payload)

    return {
        "selection": selection,
        "authoritative": authoritative_payloads,
        "uncertain": uncertain_payloads,
        "selected_fact_ids": selected_ids,
        "expired_temporary_ids": expired_temporary_ids,
        "suppressed_uncertain_ids": suppressed_uncertain_ids,
        "omitted_due_to_limit_ids": omitted_due_to_limit_ids,
        "eligible_count": len(candidates),
    }


def _sorted_facts(facts: Iterable[CampaignFact]) -> List[CampaignFact]:
    return sorted(
        facts,
        key=lambda fact: (
            fact.created_turn_index if isinstance(fact.created_turn_index, int) else -1,
            fact.fact_type,
            fact.fact_id,
        ),
    )


def _iter_filtered_facts(
    facts: Iterable[CampaignFact],
    *,
    authority: Optional[str],
    scope_kind: Optional[str],
    scope_ref_id: Optional[str],
) -> Iterable[CampaignFact]:
    for fact in _sorted_facts(facts):
        if isinstance(authority, str) and fact.authority != authority:
            continue
        if isinstance(scope_kind, str) and fact.scope.kind != scope_kind:
            continue
        if isinstance(scope_ref_id, str) and fact.scope.ref_id != scope_ref_id:
            continue
        yield fact


def _build_fact_from_request(
    campaign: Campaign,
    request: CampaignFactCreate,
    *,
    created_turn_index: int,
) -> CampaignFact:
    fact_id = request.fact_id or _allocate_fact_id(campaign)
    expires_turn_index = request.expires_turn_index
    if request.lifecycle == "temporary" and expires_turn_index is None:
        expires_turn_index = created_turn_index + _FACT_TEMPORARY_TTL_TURNS
    return CampaignFact(
        fact_id=fact_id,
        fact_type=request.fact_type,
        summary=request.summary,
        content=request.content,
        source=request.source.model_copy(deep=True),
        authority=request.authority,
        reliability=request.reliability,
        scope=request.scope.model_copy(deep=True),
        lifecycle=request.lifecycle,
        expires_turn_index=expires_turn_index,
        created_turn_index=created_turn_index,
        metadata=dict(request.metadata),
    )


def _allocate_fact_id(campaign: Campaign) -> str:
    for _ in range(256):
        candidate = f"fact_{uuid4().hex[:12]}"
        if candidate not in campaign.facts:
            return candidate
    raise RuntimeError("Failed to allocate fact_id.")


def _find_exact_duplicate(
    facts: Iterable[CampaignFact], candidate: CampaignFact
) -> Optional[CampaignFact]:
    signature = _duplicate_signature(candidate)
    for fact in facts:
        if _duplicate_signature(fact) == signature:
            return fact
    return None


def _duplicate_signature(fact: CampaignFact) -> tuple[str, ...]:
    return (
        fact.fact_type,
        fact.summary.strip().lower(),
        fact.content.strip().lower(),
        fact.source.kind,
        fact.source.ref_id or "",
        fact.source.actor_id or "",
        fact.authority,
        fact.reliability,
        fact.scope.kind,
        fact.scope.ref_id or "",
        fact.lifecycle,
        str(fact.expires_turn_index or ""),
    )


def _resolve_current_turn_index(
    campaign: Campaign,
    *,
    current_turn_index: Optional[int],
) -> int:
    if isinstance(current_turn_index, int):
        return current_turn_index
    indices = [
        fact.created_turn_index
        for fact in campaign.facts.values()
        if isinstance(fact.created_turn_index, int)
    ]
    if not indices:
        return 0
    return max(indices) + 1


def _effective_expiry_turn_index(fact: CampaignFact) -> Optional[int]:
    if fact.lifecycle != "temporary":
        return None
    if isinstance(fact.expires_turn_index, int):
        return fact.expires_turn_index
    if isinstance(fact.created_turn_index, int):
        return fact.created_turn_index + _FACT_TEMPORARY_TTL_TURNS
    return _FACT_TEMPORARY_TTL_TURNS


def _is_expired_temporary_fact(
    fact: CampaignFact,
    *,
    current_turn_index: int,
) -> bool:
    expiry = _effective_expiry_turn_index(fact)
    if expiry is None:
        return False
    return current_turn_index > expiry


def _conflict_key(fact: CampaignFact) -> tuple[str, str, str]:
    return (fact.fact_type, fact.scope.kind, fact.scope.ref_id or "")


def _fact_is_prompt_eligible(
    fact: CampaignFact,
    *,
    effective_actor_id: str,
    active_area_id: Optional[str],
    selected_item_id: Optional[str],
    selected_scene_target_id: Optional[str],
) -> bool:
    if fact.scope.kind == "npc":
        return False
    if fact.scope.kind == "campaign":
        return True
    if fact.scope.kind == "area":
        return True
    if fact.scope.kind == "actor":
        return fact.scope.ref_id == effective_actor_id
    if fact.scope.kind == "item":
        return isinstance(selected_item_id, str) and fact.scope.ref_id == selected_item_id
    if fact.scope.kind == "entity":
        return isinstance(selected_scene_target_id, str) and (
            fact.scope.ref_id == selected_scene_target_id
        )
    return isinstance(active_area_id, str) and fact.scope.ref_id == active_area_id


def _prompt_scope_bucket(
    fact: CampaignFact,
    *,
    effective_actor_id: str,
    active_area_id: Optional[str],
    selected_item_id: Optional[str],
    selected_scene_target_id: Optional[str],
) -> str:
    if fact.scope.kind == "campaign":
        return "campaign"
    if fact.scope.kind == "area":
        if isinstance(active_area_id, str) and fact.scope.ref_id == active_area_id:
            return "area_current"
        return "area_other"
    if fact.scope.kind == "actor":
        if fact.scope.ref_id == effective_actor_id:
            return "actor_current"
        return "area_other"
    if fact.scope.kind == "item":
        if isinstance(selected_item_id, str) and fact.scope.ref_id == selected_item_id:
            return "item_selected"
        return "area_other"
    if fact.scope.kind == "npc":
        if (
            isinstance(selected_scene_target_id, str)
            and fact.scope.ref_id == selected_scene_target_id
        ):
            return "npc_selected"
        return "area_other"
    if (
        isinstance(selected_scene_target_id, str)
        and fact.scope.kind == "entity"
        and fact.scope.ref_id == selected_scene_target_id
    ):
        return "entity_selected"
    return "area_other"


def _select_npc_memory_facts(
    campaign: Campaign,
    *,
    npc_id: str,
    current_turn_index: Optional[int],
    max_items: int,
) -> Dict[str, object]:
    resolved_turn_index = _resolve_current_turn_index(
        campaign, current_turn_index=current_turn_index
    )
    candidates: List[CampaignFact] = []
    expired_fact_ids: List[str] = []
    for fact in _sorted_facts(campaign.facts.values()):
        if fact.fact_type != "npc_memory":
            continue
        if fact.scope.kind != "npc" or fact.scope.ref_id != npc_id:
            continue
        if _is_expired_temporary_fact(fact, current_turn_index=resolved_turn_index):
            expired_fact_ids.append(fact.fact_id)
            continue
        candidates.append(fact)

    candidates.sort(key=_npc_memory_rank)
    selected = candidates[: max(0, max_items)]
    return {
        "items": [_npc_memory_prompt_payload(fact) for fact in selected],
        "fact_ids": [fact.fact_id for fact in selected],
        "expired_fact_ids": expired_fact_ids,
        "omitted_due_to_limit_ids": [
            fact.fact_id for fact in candidates[max(0, max_items) :]
        ],
    }


def _prompt_rank(
    fact: CampaignFact,
    *,
    effective_actor_id: str,
    active_area_id: Optional[str],
    selected_item_id: Optional[str],
    selected_scene_target_id: Optional[str],
) -> tuple[int, int, int, int, str]:
    scope_bucket = _prompt_scope_bucket(
        fact,
        effective_actor_id=effective_actor_id,
        active_area_id=active_area_id,
        selected_item_id=selected_item_id,
        selected_scene_target_id=selected_scene_target_id,
    )
    return (
        0 if fact.authority == "authoritative" else 1,
        _PROMPT_SCOPE_PRIORITY.get(scope_bucket, 99),
        -(fact.created_turn_index if isinstance(fact.created_turn_index, int) else -1),
        0 if fact.lifecycle == "persistent" else 1,
        fact.fact_id,
    )


def _npc_memory_rank(fact: CampaignFact) -> tuple[int, int, str]:
    return (
        0 if fact.authority == "authoritative" else 1,
        -(fact.created_turn_index if isinstance(fact.created_turn_index, int) else -1),
        fact.fact_id,
    )


def _temporary_prune_rank(fact: CampaignFact) -> tuple[int, int, int, str]:
    return (
        0 if fact.authority == "uncertain" else 1,
        _RELIABILITY_PRUNE_PRIORITY.get(fact.reliability, 99),
        fact.created_turn_index if isinstance(fact.created_turn_index, int) else 0,
        fact.fact_id,
    )


def _fact_prompt_payload(fact: CampaignFact) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "fact_id": fact.fact_id,
        "fact_type": fact.fact_type,
        "summary": fact.summary,
        "source": fact.source.model_dump(),
        "authority": fact.authority,
        "reliability": fact.reliability,
        "scope": fact.scope.model_dump(),
        "lifecycle": fact.lifecycle,
        "created_turn_index": fact.created_turn_index,
    }
    if isinstance(fact.expires_turn_index, int):
        payload["expires_turn_index"] = fact.expires_turn_index
    if fact.content:
        payload["content"] = fact.content
    return payload


def _npc_memory_prompt_payload(fact: CampaignFact) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "summary": fact.summary,
        "reliability": fact.reliability,
        "created_turn_index": fact.created_turn_index,
    }
    if isinstance(fact.metadata, dict):
        npc_label = fact.metadata.get("npc_label")
        if isinstance(npc_label, str) and npc_label.strip():
            payload["npc_label"] = npc_label.strip()
    return payload


def _build_npc_memory_summary(user_input: str) -> Optional[str]:
    if not isinstance(user_input, str):
        return None
    collapsed = " ".join(user_input.strip().split())
    if not collapsed:
        return None
    lowered = collapsed.lower()
    if " about " in lowered:
        marker = lowered.index(" about ")
        topic = collapsed[marker + len(" about ") :].strip()
    else:
        topic = collapsed
    topic = topic.strip(" \t\r\n.:;!?\"'")
    topic = re.sub(r"^(the|a|an)\s+", "", topic, flags=re.IGNORECASE)
    if not topic:
        return None
    if len(topic) > _NPC_MEMORY_MAX_SUMMARY_CHARS:
        topic = topic[: _NPC_MEMORY_MAX_SUMMARY_CHARS - 3].rstrip() + "..."
    return f"Previous topic: {topic}"


def _turn_id_to_number(turn_id: str) -> int:
    if not isinstance(turn_id, str):
        return 0
    if "_" not in turn_id:
        return 0
    suffix = turn_id.split("_", 1)[1]
    if not suffix.isdigit():
        return 0
    return int(suffix)
