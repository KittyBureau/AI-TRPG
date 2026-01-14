from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.models import AppliedAction, ConflictItem, ToolFeedback


def detect_conflicts(
    narrative_text: str,
    applied_actions: List[AppliedAction],
    tool_feedback: Optional[ToolFeedback],
    state_before: Dict[str, Any],
    state_after: Dict[str, Any],
) -> List[ConflictItem]:
    conflicts: List[ConflictItem] = []
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
        conflicts.extend(_detect_failed_tool_mentions(lowered, tool_feedback))

    conflicts.extend(_detect_state_claim_mismatch(lowered, state_after))

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


def _extract_snippet(text: str, keyword: str) -> str:
    index = text.find(keyword)
    if index == -1:
        return keyword
    start = max(0, index - 20)
    end = min(len(text), index + 20)
    return text[start:end]
