from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from backend.domain.models import (
    Campaign,
    CampaignHostilityOutcome,
    CampaignHostilityState,
    CampaignHostilityTarget,
    Entity,
)

_HOSTILITY_THRESHOLD = 2
_LOCKABLE_ACTIONS_BY_KIND = {
    "npc": {"talk"},
    "container": {"search"},
}
_VERBAL_AGGRESSION_MARKERS = {
    "aggressive",
    "hostile",
    "intimidate",
    "intimidating",
    "threaten",
    "threatening",
}
_ASSAULTIVE_INTENT_MARKERS = {
    "assault",
    "attack",
    "hit",
    "hurt",
    "strike",
    "violence",
    "violent",
}


def record_hostility_scene_action(
    campaign: Campaign,
    *,
    action: str,
    target: Optional[Entity],
    params: Dict[str, object],
) -> Optional[Dict[str, object]]:
    if target is None:
        return None
    lockable_actions = _LOCKABLE_ACTIONS_BY_KIND.get(target.kind, set())
    if action not in lockable_actions:
        return None
    category, delta = _classify_hostility(params)
    if category is None or delta <= 0:
        return None

    state = _state(campaign)
    target_state = state.targets.get(target.id)
    if target_state is None:
        target_state = CampaignHostilityTarget(
            target_id=target.id,
            threshold=_HOSTILITY_THRESHOLD,
        )
        state.targets[target.id] = target_state

    target_state.score += delta
    target_state.last_category = category

    triggered_outcomes: list[CampaignHostilityOutcome] = []
    if (
        target_state.score >= target_state.threshold
        and not target_state.interaction_locked
    ):
        target_state.interaction_locked = True
        _lock_entity_interaction(target, blocked_action=action)
        outcome_id = f"hostility_{target.id}_interaction_locked"
        outcome = state.outcomes.get(outcome_id)
        if outcome is None:
            outcome = CampaignHostilityOutcome(
                outcome_id=outcome_id,
                type="interaction_locked",
                target_id=target.id,
            )
            state.outcomes[outcome_id] = outcome
        if outcome_id not in target_state.triggered_outcome_ids:
            target_state.triggered_outcome_ids.append(outcome_id)
        triggered_outcomes.append(outcome)
        progression_outcome = _maybe_trigger_progression_locked(
            campaign,
            state=state,
            target_state=target_state,
            target_id=target.id,
            blocked_action=action,
        )
        if progression_outcome is not None:
            triggered_outcomes.append(progression_outcome)

    return _build_target_payload(target_state, triggered_outcomes=triggered_outcomes, delta=delta)


def build_hostility_state_summary(campaign: Campaign) -> Dict[str, object]:
    state = _state(campaign)
    targets = [
        _build_target_payload(target_state)
        for target_state in sorted(state.targets.values(), key=lambda item: item.target_id)
    ]
    outcomes = [
        {
            "outcome_id": outcome.outcome_id,
            "type": outcome.type,
            "target_id": outcome.target_id,
            "scope_kind": outcome.scope_kind,
            "active": outcome.active,
        }
        for outcome in sorted(state.outcomes.values(), key=lambda item: item.outcome_id)
    ]
    return {
        "target_count": len(targets),
        "outcome_count": len(outcomes),
        "targets": targets,
        "outcomes": outcomes,
    }


def build_target_hostility_snapshot(
    campaign: Campaign,
    *,
    target_id: str,
) -> Optional[Dict[str, object]]:
    state = _state(campaign)
    target_state = state.targets.get(target_id)
    if target_state is None:
        return None
    outcomes = [
        outcome
        for outcome in state.outcomes.values()
        if outcome.target_id == target_id and outcome.active
    ]
    return _build_target_payload(target_state, triggered_outcomes=outcomes)


def _classify_hostility(params: Dict[str, object]) -> tuple[Optional[str], int]:
    values = {
        _normalize_marker(params.get("intent")),
        _normalize_marker(params.get("tone")),
        _normalize_marker(params.get("approach")),
    }
    values.discard("")
    if values & _ASSAULTIVE_INTENT_MARKERS:
        return "assaultive_intent", 2
    if values & _VERBAL_AGGRESSION_MARKERS:
        return "verbal_aggression", 1
    return None, 0


def _normalize_marker(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _lock_entity_interaction(target: Entity, *, blocked_action: str) -> None:
    target.state["interaction_locked"] = True
    blocked_verbs = [
        verb
        for verb in target.state.get("blocked_verbs", [])
        if isinstance(verb, str) and verb.strip()
    ]
    if blocked_action not in blocked_verbs:
        blocked_verbs.append(blocked_action)
    target.state["blocked_verbs"] = blocked_verbs


def _maybe_trigger_progression_locked(
    campaign: Campaign,
    *,
    state: CampaignHostilityState,
    target_state: CampaignHostilityTarget,
    target_id: str,
    blocked_action: str,
) -> Optional[CampaignHostilityOutcome]:
    if campaign.lifecycle.ended:
        return None
    fragment = campaign.scenario_runtime_fragment
    if fragment is None or fragment.template_id != "key_gate_scenario":
        return None
    critical_source_id = fragment.revealed_item.source_interactable_id
    critical_interaction = fragment.revealed_item.reveal_interaction
    required_item_id = fragment.gate.required_item_id
    if target_id != critical_source_id or blocked_action != critical_interaction:
        return None
    if _required_item_still_available(campaign, required_item_id):
        return None

    outcome_id = f"hostility_{target_id}_progression_locked"
    outcome = state.outcomes.get(outcome_id)
    if outcome is None:
        outcome = CampaignHostilityOutcome(
            outcome_id=outcome_id,
            type="progression_locked",
            target_id=target_id,
        )
        state.outcomes[outcome_id] = outcome
    if outcome_id not in target_state.triggered_outcome_ids:
        target_state.triggered_outcome_ids.append(outcome_id)

    campaign.goal.status = "failed"
    campaign.lifecycle.ended = True
    campaign.lifecycle.reason = "progression_locked"
    if campaign.lifecycle.ended_at is None:
        campaign.lifecycle.ended_at = datetime.now(timezone.utc).isoformat()
    return outcome


def _required_item_still_available(campaign: Campaign, required_item_id: str) -> bool:
    return any(
        stack.definition_id == required_item_id for stack in campaign.items.values()
    )


def _build_target_payload(
    target_state: CampaignHostilityTarget,
    *,
    triggered_outcomes: Optional[list[CampaignHostilityOutcome]] = None,
    delta: int = 0,
) -> Dict[str, object]:
    payload = {
        "target_id": target_state.target_id,
        "scope_kind": target_state.scope_kind,
        "score": target_state.score,
        "threshold": target_state.threshold,
        "interaction_locked": target_state.interaction_locked,
        "last_category": target_state.last_category or "",
        "triggered_outcome_ids": list(target_state.triggered_outcome_ids),
    }
    if delta > 0:
        payload["delta"] = delta
    if triggered_outcomes:
        payload["triggered_outcomes"] = [
            {
                "outcome_id": outcome.outcome_id,
                "type": outcome.type,
                "target_id": outcome.target_id,
                "scope_kind": outcome.scope_kind,
                "active": outcome.active,
            }
            for outcome in triggered_outcomes
        ]
    return payload


def _state(campaign: Campaign) -> CampaignHostilityState:
    state = getattr(campaign, "hostility", None)
    if isinstance(state, CampaignHostilityState):
        return state
    normalized = CampaignHostilityState.model_validate(state or {})
    campaign.hostility = normalized
    return normalized
