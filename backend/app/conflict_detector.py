from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from backend.domain.models import AppliedAction, ConflictItem, ToolFeedback

ENABLE_TEXT_CONFLICT_CHECKS = (
    os.getenv("CONFLICT_TEXT_CHECKS", "0").strip().lower() in {"1", "true", "yes"}
)


def detect_conflicts(
    narrative_text: str,
    dialog_type: str,
    applied_actions: List[AppliedAction],
    tool_feedback: Optional[ToolFeedback],
    state_before: Dict[str, Any],
    state_after: Dict[str, Any],
) -> List[ConflictItem]:
    conflicts: List[ConflictItem] = []
    tool_activity = bool(applied_actions) or bool(
        tool_feedback and tool_feedback.failed_calls
    )

    if ENABLE_TEXT_CONFLICT_CHECKS:
        lowered = narrative_text.lower()

        if _mentions_forbidden_change(lowered):
            conflicts.append(
                ConflictItem(
                    type="forbidden_change",
                    field="rules_or_world",
                    expected="no_rule_or_world_change",
                    found_in_text=_extract_snippet(lowered, "rule"),
                )
            )

        if dialog_type != "rule_explanation":
            if _mentions_state_change(lowered) and not applied_actions:
                conflicts.append(
                    ConflictItem(
                        type="state_mismatch",
                        field="applied_actions",
                        expected="no_state_change",
                        found_in_text=_extract_snippet(lowered, "move"),
                    )
                )

            if tool_feedback:
                conflicts.extend(
                    _detect_failed_tool_mentions(lowered, tool_feedback)
                )

            conflicts.extend(_detect_state_claim_mismatch(lowered, state_after))

        return conflicts

    if tool_activity:
        conflicts.extend(
            _detect_tool_state_mismatch(
                applied_actions, tool_feedback, state_before, state_after
            )
        )

    return conflicts


def _mentions_forbidden_change(text: str) -> bool:
    keywords = [
        "change the rules",
        "rewrite the rules",
        "new rule",
        "rules updated",
        "map changed",
        "world changed",
        "timeline changed",
    ]
    return any(keyword in text for keyword in keywords)


def _mentions_state_change(text: str) -> bool:
    keywords = [
        "move",
        "moved",
        "move to",
        "arrive",
        "arrives",
        "enter",
        "entered",
        "hp",
        "health",
        "damage",
        "heal",
        "dies",
        "dead",
    ]
    return any(keyword in text for keyword in keywords)


def _detect_failed_tool_mentions(
    text: str, tool_feedback: ToolFeedback
) -> List[ConflictItem]:
    conflicts: List[ConflictItem] = []
    tool_keywords = {
        "move": ["move", "moved", "arrive", "enter"],
        "hp_delta": ["hp", "health", "damage", "heal"],
        "map_generate": ["map", "area", "room"],
    }
    for failed in tool_feedback.failed_calls:
        keywords = tool_keywords.get(failed.tool, [])
        if any(keyword in text for keyword in keywords):
            conflicts.append(
                ConflictItem(
                    type="tool_result_mismatch",
                    field=failed.tool,
                    expected="tool_failed",
                    found_in_text=_extract_snippet(text, keywords[0] if keywords else failed.tool),
                )
            )
    return conflicts


def _detect_state_claim_mismatch(
    text: str, state_after: Dict[str, Any]
) -> List[ConflictItem]:
    conflicts: List[ConflictItem] = []
    character_states = state_after.get("character_states", {})
    if "dead" in text or "dies" in text:
        if not any(state == "dead" for state in character_states.values()):
            conflicts.append(
                ConflictItem(
                    type="state_mismatch",
                    field="character_states",
                    expected="no_dead_state",
                    found_in_text=_extract_snippet(text, "dead"),
                )
            )
    return conflicts


def _detect_tool_state_mismatch(
    applied_actions: List[AppliedAction],
    tool_feedback: Optional[ToolFeedback],
    state_before: Dict[str, Any],
    state_after: Dict[str, Any],
) -> List[ConflictItem]:
    conflicts: List[ConflictItem] = []
    before_positions = state_before.get("positions", {})
    before_hp = state_before.get("hp", {})
    before_character_states = state_before.get("character_states", {})
    after_positions = state_after.get("positions", {})
    after_positions_parent = state_after.get("positions_parent", {})
    after_hp = state_after.get("hp", {})
    after_character_states = state_after.get("character_states", {})

    if tool_feedback and tool_feedback.failed_calls and not applied_actions:
        if (
            before_positions != after_positions
            or before_hp != after_hp
            or before_character_states != after_character_states
        ):
            conflicts.append(
                ConflictItem(
                    type="state_mismatch",
                    field="applied_actions",
                    expected="no_state_change",
                    found_in_text="state_changed_without_actions",
                )
            )
        return conflicts

    for action in applied_actions:
        if action.tool == "move":
            actor_id = action.args.get("actor_id")
            to_area_id = action.result.get("to_area_id")
            if not isinstance(actor_id, str) or not isinstance(to_area_id, str):
                conflicts.append(
                    ConflictItem(
                        type="tool_result_mismatch",
                        field="move",
                        expected="valid_move_result",
                        found_in_text="invalid_move_payload",
                    )
                )
                continue
            if after_positions.get(actor_id) != to_area_id:
                conflicts.append(
                    ConflictItem(
                        type="tool_result_mismatch",
                        field="move",
                        expected=to_area_id,
                        found_in_text=str(after_positions.get(actor_id)),
                    )
                )
            if after_positions_parent.get(actor_id) != to_area_id:
                conflicts.append(
                    ConflictItem(
                        type="tool_result_mismatch",
                        field="move_parent",
                        expected=to_area_id,
                        found_in_text=str(after_positions_parent.get(actor_id)),
                    )
                )
        elif action.tool == "hp_delta":
            target_id = action.args.get("target_character_id")
            new_hp = action.result.get("new_hp")
            if not isinstance(target_id, str) or not isinstance(new_hp, int):
                conflicts.append(
                    ConflictItem(
                        type="tool_result_mismatch",
                        field="hp_delta",
                        expected="valid_hp_result",
                        found_in_text="invalid_hp_payload",
                    )
                )
                continue
            if after_hp.get(target_id) != new_hp:
                conflicts.append(
                    ConflictItem(
                        type="tool_result_mismatch",
                        field="hp_delta",
                        expected=str(new_hp),
                        found_in_text=str(after_hp.get(target_id)),
                    )
                )

    return conflicts


def _extract_snippet(text: str, keyword: str) -> str:
    index = text.find(keyword)
    if index == -1:
        return keyword
    start = max(0, index - 20)
    end = min(len(text), index + 20)
    return text[start:end]
