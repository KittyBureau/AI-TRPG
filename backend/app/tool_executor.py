from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from backend.domain.models import (
    AppliedAction,
    Campaign,
    FailedCall,
    ToolCall,
    ToolFeedback,
)
from backend.domain.state_machine import resolve_tool_permission


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
    campaign.positions[actor_id] = to_area_id
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
    parent_area_id = call.args.get("parent_area_id")
    if not isinstance(parent_area_id, str):
        return None
    if parent_area_id not in campaign.map.areas:
        return None

    next_index = len(campaign.map.areas) + 1
    new_area_id = f"area_{next_index:03d}"
    from backend.domain.models import MapArea

    campaign.map.areas[new_area_id] = MapArea(
        id=new_area_id,
        name="Generated Area",
        parent_area_id=parent_area_id,
    )
    campaign.map.connections.append(
        _connection(parent_area_id, new_area_id)
    )
    return AppliedAction(
        tool="map_generate",
        args=call.args,
        result={"new_area_id": new_area_id},
        timestamp=timestamp,
    )


def _is_connected(campaign: Campaign, from_area_id: str, to_area_id: str) -> bool:
    for connection in campaign.map.connections:
        if connection.from_area_id == from_area_id and connection.to_area_id == to_area_id:
            return True
        if connection.from_area_id == to_area_id and connection.to_area_id == from_area_id:
            return True
    return False


def _connection(from_area_id: str, to_area_id: str):
    from backend.domain.models import MapConnection

    return MapConnection(from_area_id=from_area_id, to_area_id=to_area_id)
