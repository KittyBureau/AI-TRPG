from __future__ import annotations

import warnings
from typing import Dict, Optional, Tuple

from backend.domain.models import ActorState, Campaign, MapData

DEFAULT_HP = 10
DEFAULT_CHARACTER_STATE = "alive"


def ensure_actor(campaign: Campaign, actor_id: str) -> ActorState:
    if not isinstance(campaign.actors, dict):
        campaign.actors = {}
    actor = campaign.actors.get(actor_id)
    if isinstance(actor, ActorState):
        return actor
    if isinstance(actor, dict):
        try:
            actor = ActorState(**actor)
        except Exception:
            actor = ActorState()
    else:
        actor = ActorState()
    campaign.actors[actor_id] = actor
    return actor


def update_actor_position(
    campaign: Campaign, actor_id: str, area_id: Optional[str]
) -> None:
    actor = ensure_actor(campaign, actor_id)
    actor.position = area_id


def validate_actors_state(
    campaign: Campaign, map_data: Optional[MapData] = None
) -> bool:
    updated = False
    if not isinstance(campaign.actors, dict):
        campaign.actors = {}
        updated = True

    for actor_id in list(campaign.actors.keys()):
        actor = campaign.actors[actor_id]
        if not isinstance(actor, ActorState):
            if isinstance(actor, dict):
                try:
                    actor = ActorState(**actor)
                except Exception:
                    actor = ActorState()
            else:
                actor = ActorState()
            campaign.actors[actor_id] = actor
            updated = True

        if actor.position is not None and not isinstance(actor.position, str):
            actor.position = None
            updated = True
        if not isinstance(actor.hp, int):
            actor.hp = DEFAULT_HP
            updated = True
        if actor.hp < 0:
            actor.hp = 0
            updated = True
        if not isinstance(actor.character_state, str):
            actor.character_state = DEFAULT_CHARACTER_STATE
            updated = True
        if not isinstance(actor.meta, dict):
            actor.meta = {}
            updated = True

        if map_data and actor.position is not None:
            if actor.position not in map_data.areas:
                warnings.warn(
                    f"Unknown area_id for actor {actor_id}: {actor.position}",
                    RuntimeWarning,
                )
                actor.position = None
                updated = True

    return updated


def derive_state_maps(
    campaign: Campaign,
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, Optional[str]], Dict[str, int], Dict[str, str]]:
    positions: Dict[str, str] = {}
    hp: Dict[str, int] = {}
    character_states: Dict[str, str] = {}
    positions_child: Dict[str, Optional[str]] = {}
    for actor_id, actor in campaign.actors.items():
        if not isinstance(actor, ActorState):
            actor = ensure_actor(campaign, actor_id)
        if actor.position is not None:
            positions[actor_id] = actor.position
        hp[actor_id] = actor.hp
        character_states[actor_id] = actor.character_state
        positions_child[actor_id] = None
    return positions, dict(positions), positions_child, hp, character_states
