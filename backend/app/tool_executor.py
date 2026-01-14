from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from backend.domain.models import (
    AppliedAction,
    Campaign,
    FailedCall,
    ToolCall,
    ToolFeedback,
)
from backend.domain.map_models import normalize_map, require_valid_map
from backend.domain.state_machine import resolve_tool_permission
from backend.domain.state_utils import set_parent_position
from backend.infra.map_generators.deterministic_generator import (
    DeterministicMapGenerator,
)


def execute_tool_calls(
    campaign: Campaign,
    actor_id: str,
    tool_calls: List[ToolCall],
) -> Tuple[List[AppliedAction], Optional[ToolFeedback]]:
    applied_actions: List[AppliedAction] = []
    failed_calls: List[FailedCall] = []

    for call in tool_calls:
        if call.tool not in campaign.allowlist:
            failed_calls.append(
                FailedCall(
                    id=call.id,
                    tool=call.tool,
                    status="rejected",
                    reason="tool_not_allowed",
                )
            )
            continue

        allowed, reason = _check_state_permission(campaign, actor_id, call)
        if not allowed:
            failed_calls.append(
                FailedCall(
                    id=call.id,
                    tool=call.tool,
                    status="rejected",
                    reason=reason,
                )
            )
            continue

        action = _apply_tool_call(campaign, actor_id, call)
        if action is None:
            failed_calls.append(
                FailedCall(
                    id=call.id,
                    tool=call.tool,
                    status="error",
                    reason="invalid_args",
                )
            )
            continue

        applied_actions.append(action)

    tool_feedback = ToolFeedback(failed_calls=failed_calls) if failed_calls else None
    return applied_actions, tool_feedback


def _check_state_permission(
    campaign: Campaign, actor_id: str, call: ToolCall
) -> Tuple[bool, str]:
    actor_state = campaign.character_states.get(actor_id, "alive")
    target_is_actor = False
    hp_delta: Optional[int] = None
    if call.tool == "hp_delta":
        target_is_actor = call.args.get("target_character_id") == actor_id
        delta = call.args.get("delta")
        if isinstance(delta, int):
            hp_delta = delta

    return resolve_tool_permission(
        actor_state, call.tool, target_is_actor=target_is_actor, hp_delta=hp_delta
    )


def _apply_tool_call(
    campaign: Campaign, actor_id: str, call: ToolCall
) -> Optional[AppliedAction]:
    timestamp = datetime.now(timezone.utc).isoformat()
    if call.tool == "move":
        return _apply_move(campaign, actor_id, call, timestamp)
    if call.tool == "hp_delta":
        return _apply_hp_delta(campaign, call, timestamp)
    if call.tool == "map_generate":
        return _apply_map_generate(campaign, call, timestamp)
    return None


def _apply_move(
    campaign: Campaign, active_actor_id: str, call: ToolCall, timestamp: str
) -> Optional[AppliedAction]:
    actor_id = call.args.get("actor_id")
    from_area_id = call.args.get("from_area_id")
    to_area_id = call.args.get("to_area_id")
    if not all(isinstance(value, str) for value in [actor_id, from_area_id, to_area_id]):
        return None
    if actor_id != active_actor_id:
        return None
    if actor_id not in campaign.positions:
        return None
    if campaign.positions.get(actor_id) != from_area_id:
        return None
    if not _is_connected(campaign, from_area_id, to_area_id):
        return None
    set_parent_position(campaign, actor_id, to_area_id)
    return AppliedAction(
        tool="move",
        args=call.args,
        result={"to_area_id": to_area_id},
        timestamp=timestamp,
    )


def _apply_hp_delta(
    campaign: Campaign, call: ToolCall, timestamp: str
) -> Optional[AppliedAction]:
    target_id = call.args.get("target_character_id")
    delta = call.args.get("delta")
    cause = call.args.get("cause")
    if not isinstance(target_id, str) or not isinstance(delta, int):
        return None
    if not isinstance(cause, str):
        return None
    if target_id not in campaign.hp:
        return None

    new_hp = campaign.hp[target_id] + delta
    campaign.hp[target_id] = new_hp
    if campaign.settings_snapshot.rules.hp_zero_ends_game:
        if new_hp <= 0:
            campaign.character_states[target_id] = "dying"
        elif campaign.character_states.get(target_id) == "dying":
            campaign.character_states[target_id] = "alive"
    return AppliedAction(
        tool="hp_delta",
        args=call.args,
        result={"new_hp": new_hp},
        timestamp=timestamp,
    )


def _apply_map_generate(
    campaign: Campaign, call: ToolCall, timestamp: str
) -> Optional[AppliedAction]:
    parent_area_id = call.args.get("parent_area_id", None)
    if parent_area_id is not None and not isinstance(parent_area_id, str):
        return None
    if parent_area_id is not None and parent_area_id not in campaign.map.areas:
        return None

    theme = call.args.get("theme", "Generated")
    if theme is None:
        theme = "Generated"
    if not isinstance(theme, str):
        return None

    constraints = call.args.get("constraints")
    size = 6
    seed: Optional[str] = None
    if isinstance(constraints, dict):
        if "size" in constraints:
            size_value = constraints.get("size")
            if not isinstance(size_value, int):
                return None
            size = size_value
        if "seed" in constraints:
            seed_value = constraints.get("seed")
            if seed_value is not None and not isinstance(seed_value, str):
                return None
            seed = seed_value
    elif constraints is not None:
        return None
    else:
        if "size" in call.args:
            size_value = call.args.get("size")
            if not isinstance(size_value, int):
                return None
            size = size_value
        if "seed" in call.args:
            seed_value = call.args.get("seed")
            if seed_value is not None and not isinstance(seed_value, str):
                return None
            seed = seed_value

    if size < 1 or size > 30:
        return None

    if hasattr(campaign.map, "model_copy"):
        snapshot = campaign.map.model_copy(deep=True)
    elif hasattr(campaign.map, "copy"):
        snapshot = campaign.map.copy(deep=True)
    else:
        snapshot = deepcopy(campaign.map)

    before_connections = sum(
        len(area.reachable_area_ids) for area in campaign.map.areas.values()
    )

    generator = DeterministicMapGenerator()
    result = generator.generate(
        campaign.map, parent_area_id, theme, size, seed
    )

    for area_id, area in result.new_areas.items():
        campaign.map.areas[area_id] = area
    for from_id, to_id in result.new_edges:
        if from_id not in campaign.map.areas or to_id not in campaign.map.areas:
            campaign.map = snapshot
            return None
        reachable = campaign.map.areas[from_id].reachable_area_ids
        if to_id not in reachable:
            reachable.append(to_id)

    try:
        require_valid_map(campaign.map)
    except ValueError:
        campaign.map = snapshot
        return None

    normalize_map(campaign.map)
    after_connections = sum(
        len(area.reachable_area_ids) for area in campaign.map.areas.values()
    )
    return AppliedAction(
        tool="map_generate",
        args=call.args,
        result={
            "created_area_ids": result.created_area_ids,
            "created_connections": after_connections - before_connections,
            "root_parent_area_id": parent_area_id,
            "warnings": result.warnings,
        },
        timestamp=timestamp,
    )


def _is_connected(campaign: Campaign, from_area_id: str, to_area_id: str) -> bool:
    area = campaign.map.areas.get(from_area_id)
    if not area:
        return False
    return to_area_id in area.reachable_area_ids
