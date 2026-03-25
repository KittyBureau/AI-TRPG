from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from backend.domain.consequence_models import (
    CampaignConsequence,
    CampaignConsequenceCreate,
    CampaignConsequenceState,
)
from backend.domain.mistake_models import CampaignMistakeSignal
from backend.domain.models import Campaign

_CONSEQUENCE_LEVEL_LIMIT = 2


def refresh_campaign_consequences(campaign: Campaign) -> Dict[str, List[str]]:
    previous_state = _state(campaign)
    previous_entries = dict(previous_state.entries)
    draft_entries = _derive_consequence_drafts(campaign)
    now = datetime.now(timezone.utc).isoformat()

    next_entries: Dict[str, CampaignConsequence] = {}
    triggered_ids: List[str] = []
    source_signal_ids: set[str] = set()

    for consequence_id, draft in draft_entries.items():
        previous = previous_entries.get(consequence_id)
        if previous is None:
            entry = CampaignConsequence(
                consequence_id=consequence_id,
                created_at=now,
                updated_at=now,
                **draft.model_dump(),
            )
            triggered_ids.append(consequence_id)
        else:
            payload = draft.model_dump()
            entry = CampaignConsequence(
                consequence_id=consequence_id,
                created_at=previous.created_at,
                updated_at=now if _entry_signature(previous) != _draft_signature(draft) else previous.updated_at,
                **payload,
            )
            if _entry_signature(previous) != _entry_signature(entry):
                triggered_ids.append(consequence_id)
        next_entries[consequence_id] = entry
        if consequence_id in triggered_ids:
            source_signal_ids.update(entry.source_signal_ids)

    removed_ids = sorted(
        consequence_id
        for consequence_id in previous_entries.keys()
        if consequence_id not in next_entries
    )

    next_state = CampaignConsequenceState(entries=next_entries)
    _refresh_state_level(next_state)
    campaign.consequences = next_state
    return {
        "triggered_consequence_ids": triggered_ids,
        "removed_consequence_ids": removed_ids,
        "source_signal_ids": sorted(source_signal_ids),
    }


def build_consequence_prompt_context(
    campaign: Campaign,
    actor_id: str,
    *,
    selected_scene_target: Optional[Dict[str, object]] = None,
    max_items: int = 2,
) -> Optional[Dict[str, object]]:
    state = _state(campaign)
    if not state.entries:
        return None
    active_area_id = _active_area_id_for_actor(campaign, actor_id)
    selected_target_id = (
        selected_scene_target.get("id")
        if isinstance(selected_scene_target, dict)
        and isinstance(selected_scene_target.get("id"), str)
        else None
    )
    ranked = sorted(
        (
            entry
            for entry in state.entries.values()
            if _prompt_relevance(
                entry,
                active_area_id=active_area_id,
                selected_target_id=selected_target_id,
            )
            < 99
        ),
        key=lambda entry: _prompt_sort_key(
            entry,
            active_area_id=active_area_id,
            selected_target_id=selected_target_id,
        ),
    )
    if not ranked:
        return None
    selected_entries = ranked[: max(1, max_items)]
    return {
        "slot": "narrative_consequence_v1",
        "overall_level": state.level,
        "active_count": len(state.entries),
        "items": [_prompt_payload(entry) for entry in selected_entries],
    }


def build_consequence_debug_context(
    campaign: Campaign,
    *,
    prompt_context: Optional[Dict[str, object]] = None,
    triggered_consequence_ids: Optional[Iterable[str]] = None,
    removed_consequence_ids: Optional[Iterable[str]] = None,
    source_signal_ids: Optional[Iterable[str]] = None,
) -> Dict[str, object]:
    state = _state(campaign)
    triggered = list(triggered_consequence_ids or [])
    removed = list(removed_consequence_ids or [])
    sources = list(source_signal_ids or [])
    entries = _serialize_entries(state.entries.values())
    triggered_entries = [
        entry
        for entry in entries
        if isinstance(entry.get("consequence_id"), str)
        and entry["consequence_id"] in set(triggered)
    ]
    payload = {
        "slot": "narrative_consequence_v1",
        "level": state.level,
        "last_turn_index": state.last_turn_index,
        "active_count": len(state.entries),
        "entries": entries,
        "triggered_consequence_ids": triggered,
        "triggered_consequences": triggered_entries,
        "removed_consequence_ids": removed,
        "source_signal_ids": sources,
    }
    if isinstance(prompt_context, dict):
        payload["prompt_context"] = dict(prompt_context)
    return payload


def build_consequence_state_summary(campaign: Campaign) -> Dict[str, object]:
    state = _state(campaign)
    return {
        "level": state.level,
        "active_count": len(state.entries),
        "last_turn_index": state.last_turn_index,
        "types": sorted({entry.type for entry in state.entries.values()}),
        "tones": sorted({entry.tone for entry in state.entries.values()}),
    }


def _state(campaign: Campaign) -> CampaignConsequenceState:
    state = getattr(campaign, "consequences", None)
    if isinstance(state, CampaignConsequenceState):
        return state
    normalized = CampaignConsequenceState.model_validate(state or {})
    campaign.consequences = normalized
    return normalized


def _derive_consequence_drafts(
    campaign: Campaign,
) -> Dict[str, CampaignConsequenceCreate]:
    entries: Dict[str, CampaignConsequenceCreate] = {}
    mistakes = getattr(campaign, "mistakes", None)
    mistake_entries = (
        mistakes.entries.values() if mistakes is not None and hasattr(mistakes, "entries") else []
    )
    for mistake in mistake_entries:
        if not isinstance(mistake, CampaignMistakeSignal):
            continue
        draft = _consequence_from_mistake(campaign, mistake)
        if draft is None:
            continue
        consequence_id = _consequence_id_for(draft)
        existing = entries.get(consequence_id)
        if existing is None:
            entries[consequence_id] = draft
            continue
        entries[consequence_id] = _merge_drafts(existing, draft)
    return entries


def _consequence_from_mistake(
    campaign: Campaign,
    mistake: CampaignMistakeSignal,
) -> Optional[CampaignConsequenceCreate]:
    if mistake.count < 2 or mistake.level < 2:
        return None
    consequence_level = min(_CONSEQUENCE_LEVEL_LIMIT, max(1, mistake.level - 1))
    if mistake.category in {"wrong_item", "blocked_attempt"}:
        area_id = _consequence_area_id(campaign, mistake)
        if area_id is None:
            return None
        target_label = _display_label_for_mistake(campaign, mistake)
        tone = "watchful" if consequence_level == 1 else "tense"
        return CampaignConsequenceCreate(
            type="area_pressure",
            scope_kind="area",
            level=consequence_level,
            source_categories=[mistake.category],
            source_signal_ids=[mistake.signal_id],
            area_id=area_id,
            target_id=mistake.target_id,
            target_label=target_label,
            tone=tone,
            narrative_hint=_area_pressure_hint(target_label, tone),
            last_turn_index=mistake.last_turn_index,
        )
    if mistake.category not in {"invalid_interaction", "repeated_misuse"}:
        return None
    target_id = _normalize_optional_string(mistake.target_id)
    target = campaign.entities.get(target_id) if isinstance(target_id, str) else None
    if target is not None and target.kind == "npc":
        tone = "guarded" if consequence_level == 1 else "cold"
        return CampaignConsequenceCreate(
            type="guarded_response",
            scope_kind="npc",
            level=consequence_level,
            source_categories=[mistake.category],
            source_signal_ids=[mistake.signal_id],
            area_id=target.loc.id if target.loc.type == "area" else mistake.area_id,
            target_id=target.id,
            target_label=target.label,
            tone=tone,
            narrative_hint=_npc_guarded_hint(target.label, tone),
            last_turn_index=mistake.last_turn_index,
        )
    area_id = _consequence_area_id(campaign, mistake)
    scope_kind = "area" if isinstance(area_id, str) else "target"
    tone = "guarded" if consequence_level == 1 else "cold"
    target_label = _display_label_for_mistake(campaign, mistake)
    return CampaignConsequenceCreate(
        type="guarded_response",
        scope_kind=scope_kind,
        level=consequence_level,
        source_categories=[mistake.category],
        source_signal_ids=[mistake.signal_id],
        area_id=area_id,
        target_id=target_id if scope_kind != "area" else mistake.target_id,
        target_label=target_label,
        tone=tone,
        narrative_hint=_guarded_scene_hint(target_label, tone),
        last_turn_index=mistake.last_turn_index,
    )


def _consequence_area_id(
    campaign: Campaign,
    mistake: CampaignMistakeSignal,
) -> Optional[str]:
    area_id = _normalize_optional_string(mistake.area_id)
    if area_id is not None:
        return area_id
    target_id = _normalize_optional_string(mistake.target_id)
    if target_id is None:
        return None
    if target_id in campaign.map.areas:
        return target_id
    target = campaign.entities.get(target_id)
    if target is not None and target.loc.type == "area":
        return target.loc.id
    item = campaign.items.get(target_id)
    if item is not None and item.parent_type == "area":
        return item.parent_id
    return None


def _display_label_for_mistake(
    campaign: Campaign,
    mistake: CampaignMistakeSignal,
) -> str:
    target_label = _normalize_optional_string(mistake.target_label)
    if target_label is not None:
        return target_label
    target_id = _normalize_optional_string(mistake.target_id)
    if target_id is None:
        area_id = _normalize_optional_string(mistake.area_id)
        if area_id is not None:
            return _area_label(campaign, area_id)
        return "the scene"
    if target_id in campaign.map.areas:
        return _area_label(campaign, target_id)
    target = campaign.entities.get(target_id)
    if target is not None and isinstance(target.label, str) and target.label.strip():
        return target.label.strip()
    item = campaign.items.get(target_id)
    if item is not None and isinstance(item.label, str) and item.label.strip():
        return item.label.strip()
    return _humanize_identifier(target_id)


def _area_label(campaign: Campaign, area_id: str) -> str:
    area = campaign.map.areas.get(area_id)
    if area is not None and isinstance(area.name, str) and area.name.strip():
        return area.name.strip()
    return _humanize_identifier(area_id)


def _area_pressure_hint(label: str, tone: str) -> str:
    if tone == "tense":
        return f"The approach to {label} feels tense and watchful now."
    return f"The approach to {label} feels more watchful now."


def _npc_guarded_hint(label: str, tone: str) -> str:
    if tone == "cold":
        return f"{label} seems noticeably colder and less patient now."
    return f"{label} seems a little more guarded now."


def _guarded_scene_hint(label: str, tone: str) -> str:
    if tone == "cold":
        return f"The scene around {label} feels distinctly less patient now."
    return f"The scene around {label} feels a little more guarded now."


def _merge_drafts(
    existing: CampaignConsequenceCreate,
    incoming: CampaignConsequenceCreate,
) -> CampaignConsequenceCreate:
    merged_source_categories = sorted(
        set(existing.source_categories).union(set(incoming.source_categories))
    )
    merged_source_signal_ids = sorted(
        set(existing.source_signal_ids).union(set(incoming.source_signal_ids))
    )
    level = max(existing.level, incoming.level)
    tone = incoming.tone if incoming.level >= existing.level else existing.tone
    narrative_hint = incoming.narrative_hint if incoming.level >= existing.level else existing.narrative_hint
    return CampaignConsequenceCreate(
        type=existing.type,
        scope_kind=existing.scope_kind,
        level=level,
        source_categories=merged_source_categories,
        source_signal_ids=merged_source_signal_ids,
        area_id=incoming.area_id or existing.area_id,
        target_id=incoming.target_id or existing.target_id,
        target_label=incoming.target_label or existing.target_label,
        tone=tone,
        narrative_hint=narrative_hint,
        last_turn_index=max(existing.last_turn_index, incoming.last_turn_index),
    )


def _consequence_id_for(consequence: CampaignConsequenceCreate) -> str:
    components = [
        consequence.type,
        consequence.scope_kind,
        consequence.area_id or "",
        consequence.target_id or "",
    ]
    normalized = re.sub(r"[^a-z0-9]+", "_", "__".join(components).lower()).strip("_")
    return f"consequence_{normalized or 'entry'}"


def _entry_signature(entry: CampaignConsequence) -> tuple[object, ...]:
    return (
        entry.type,
        entry.scope_kind,
        entry.level,
        tuple(entry.source_categories),
        tuple(entry.source_signal_ids),
        entry.area_id or "",
        entry.target_id or "",
        entry.target_label or "",
        entry.tone,
        entry.narrative_hint,
        entry.last_turn_index,
    )


def _draft_signature(entry: CampaignConsequenceCreate) -> tuple[object, ...]:
    return (
        entry.type,
        entry.scope_kind,
        entry.level,
        tuple(entry.source_categories),
        tuple(entry.source_signal_ids),
        entry.area_id or "",
        entry.target_id or "",
        entry.target_label or "",
        entry.tone,
        entry.narrative_hint,
        entry.last_turn_index,
    )


def _refresh_state_level(state: CampaignConsequenceState) -> None:
    if not state.entries:
        state.level = 0
        state.last_turn_index = 0
        return
    state.level = min(
        _CONSEQUENCE_LEVEL_LIMIT,
        max(entry.level for entry in state.entries.values()),
    )
    state.last_turn_index = max(
        entry.last_turn_index for entry in state.entries.values()
    )


def _prompt_relevance(
    entry: CampaignConsequence,
    *,
    active_area_id: Optional[str],
    selected_target_id: Optional[str],
) -> int:
    if (
        isinstance(selected_target_id, str)
        and isinstance(entry.target_id, str)
        and selected_target_id == entry.target_id
    ):
        return 0
    if (
        isinstance(active_area_id, str)
        and isinstance(entry.area_id, str)
        and active_area_id == entry.area_id
    ):
        return 1
    return 99


def _prompt_sort_key(
    entry: CampaignConsequence,
    *,
    active_area_id: Optional[str],
    selected_target_id: Optional[str],
) -> tuple[int, int, int, str]:
    return (
        _prompt_relevance(
            entry,
            active_area_id=active_area_id,
            selected_target_id=selected_target_id,
        ),
        -entry.level,
        -entry.last_turn_index,
        entry.consequence_id,
    )


def _prompt_payload(entry: CampaignConsequence) -> Dict[str, object]:
    return {
        "consequence_id": entry.consequence_id,
        "type": entry.type,
        "scope_kind": entry.scope_kind,
        "level": entry.level,
        "tone": entry.tone,
        "area_id": entry.area_id or "",
        "target_id": entry.target_id or "",
        "target_label": entry.target_label or "",
        "source_categories": list(entry.source_categories),
        "recent_turn_index": entry.last_turn_index,
        "narrative_hint": entry.narrative_hint,
    }


def _serialize_entries(entries: Iterable[CampaignConsequence]) -> List[Dict[str, object]]:
    return [
        {
            "consequence_id": entry.consequence_id,
            "type": entry.type,
            "scope_kind": entry.scope_kind,
            "level": entry.level,
            "source_categories": list(entry.source_categories),
            "source_signal_ids": list(entry.source_signal_ids),
            "area_id": entry.area_id or "",
            "target_id": entry.target_id or "",
            "target_label": entry.target_label or "",
            "tone": entry.tone,
            "narrative_hint": entry.narrative_hint,
            "last_turn_index": entry.last_turn_index,
        }
        for entry in sorted(entries, key=_entry_sort_key)
    ]


def _entry_sort_key(entry: CampaignConsequence) -> tuple[int, int, str]:
    return (-entry.last_turn_index, -entry.level, entry.consequence_id)


def _active_area_id_for_actor(campaign: Campaign, actor_id: str) -> Optional[str]:
    actor = campaign.actors.get(actor_id)
    if actor is None:
        return None
    return _normalize_optional_string(actor.position)


def _normalize_optional_string(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _humanize_identifier(value: str) -> str:
    normalized = value.strip().replace("_", " ").replace("-", " ")
    if not normalized:
        return "the scene"
    return " ".join(part.capitalize() if part else "" for part in normalized.split())
