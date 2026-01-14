from __future__ import annotations

from typing import Optional, Tuple

ALLOWED_STATES = {
    "alive",
    "dying",
    "unconscious",
    "restrained_permanent",
    "dead",
}


def resolve_tool_permission(
    actor_state: str,
    tool: str,
    *,
    target_is_actor: bool,
    hp_delta: Optional[int],
) -> Tuple[bool, str]:
    if actor_state not in ALLOWED_STATES:
        return False, "invalid_actor_state"

    if actor_state == "alive":
        return True, ""

    if actor_state == "dying":
        if tool == "hp_delta" and hp_delta is not None and hp_delta > 0 and target_is_actor:
            return True, ""
        return False, "actor_state_restricted"

    if actor_state == "unconscious":
        return False, "actor_state_restricted"

    if actor_state in {"restrained_permanent", "dead"}:
        return False, "actor_state_restricted"

    return False, "actor_state_restricted"
