from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from backend.domain.models import ActorState, Campaign
from backend.domain.state_utils import DEFAULT_CHARACTER_STATE, DEFAULT_HP


def spawn_actor(
    args: Dict[str, Any],
    campaign: Campaign,
    *,
    active_actor_id: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    character_id, error = _parse_character_id(args)
    if error:
        return None, error
    bind_to_party, error = _parse_bind_to_party(args)
    if error:
        return None, error
    position, error = _resolve_spawn_position(args, campaign, active_actor_id=active_actor_id)
    if error:
        return None, error

    actor_id = _next_actor_id(campaign)
    actor = ActorState(
        position=position,
        hp=DEFAULT_HP,
        character_state=DEFAULT_CHARACTER_STATE,
        meta={"character_id": character_id},
    )
    campaign.actors[actor_id] = actor

    if bind_to_party and actor_id not in campaign.selected.party_character_ids:
        campaign.selected.party_character_ids.append(actor_id)

    if _is_null_like_active_actor_id(campaign.selected.active_actor_id):
        campaign.selected.active_actor_id = actor_id

    return {
        "actor_id": actor_id,
        "position": position,
        "hp": actor.hp,
        "created": True,
    }, None


def _parse_character_id(args: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    raw = args.get("character_id")
    if not isinstance(raw, str):
        return None, "invalid_args"
    value = raw.strip()
    if not value:
        return None, "invalid_args"
    return value, None


def _parse_bind_to_party(args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    raw = args.get("bind_to_party", True)
    if isinstance(raw, bool):
        return raw, None
    return False, "invalid_args"


def _resolve_spawn_position(
    args: Dict[str, Any],
    campaign: Campaign,
    *,
    active_actor_id: str,
) -> Tuple[Optional[str], Optional[str]]:
    if "spawn_position" in args:
        raw = args.get("spawn_position")
        if not isinstance(raw, str):
            return None, "invalid_args"
        explicit = raw.strip()
        if not explicit:
            return None, "invalid_args"
        if explicit not in campaign.map.areas:
            return None, "invalid_args"
        return explicit, None

    active_position = _active_actor_position(campaign, active_actor_id)
    if isinstance(active_position, str) and active_position in campaign.map.areas:
        return active_position, None

    if "area_001" in campaign.map.areas:
        return "area_001", None

    return None, "invalid_args"


def _active_actor_position(campaign: Campaign, active_actor_id: str) -> Optional[str]:
    actor = campaign.actors.get(active_actor_id)
    if actor is None:
        return None
    position = actor.position
    if isinstance(position, str):
        return position
    return None


def _is_null_like_active_actor_id(value: object) -> bool:
    if not isinstance(value, str):
        return True
    return not value.strip()


def _next_actor_id(campaign: Campaign) -> str:
    for _ in range(256):
        actor_id = f"actor_{uuid4().hex}"
        if actor_id not in campaign.actors:
            return actor_id
    raise RuntimeError("Failed to allocate actor_id.")
