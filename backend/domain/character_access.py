from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

from backend.domain.models import Campaign
from backend.domain.state_utils import (
    DEFAULT_CHARACTER_STATE,
    DEFAULT_HP,
    ensure_actor,
)


@dataclass
class CharacterState:
    position: Optional[str]
    hp: int
    character_state: str


@dataclass
class CharacterFact:
    character_id: str
    name: str
    role: str
    tags: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    background: str = ""
    appearance: str = ""
    personality_tags: List[str] = field(default_factory=list)


@dataclass
class CharacterView:
    character_id: str
    name: str
    role: str
    tags: List[str]
    attributes: Dict[str, Any]
    background: str
    appearance: str
    personality_tags: List[str]
    position: Optional[str]
    hp: int
    character_state: str


class CharacterStateStore(Protocol):
    def get_state(self, campaign: Campaign, character_id: str) -> CharacterState:
        ...

    def set_state(
        self, campaign: Campaign, character_id: str, state: CharacterState
    ) -> None:
        ...


class CharacterFactStore(Protocol):
    def get_fact(self, campaign: Campaign, character_id: str) -> CharacterFact:
        ...


class CampaignCharacterStateStore:
    def get_state(self, campaign: Campaign, character_id: str) -> CharacterState:
        actor = ensure_actor(campaign, character_id)
        self._ensure_legacy_maps(campaign)

        position = self._read_position(campaign, character_id, actor.position)
        hp = self._read_hp(campaign, character_id, actor.hp)
        character_state = self._read_character_state(
            campaign, character_id, actor.character_state
        )
        state = CharacterState(position=position, hp=hp, character_state=character_state)
        self._apply_state(campaign, character_id, state)
        return state

    def set_state(
        self, campaign: Campaign, character_id: str, state: CharacterState
    ) -> None:
        normalized = CharacterState(
            position=state.position if isinstance(state.position, str) else None,
            hp=self._normalize_hp(state.hp),
            character_state=(
                state.character_state
                if isinstance(state.character_state, str)
                else DEFAULT_CHARACTER_STATE
            ),
        )
        self._apply_state(campaign, character_id, normalized)

    def _apply_state(
        self, campaign: Campaign, character_id: str, state: CharacterState
    ) -> None:
        actor = ensure_actor(campaign, character_id)
        actor.position = state.position
        actor.hp = state.hp
        actor.character_state = state.character_state

        self._ensure_legacy_maps(campaign)
        if state.position is None:
            campaign.positions.pop(character_id, None)
            campaign.state.positions_parent.pop(character_id, None)
            campaign.state.positions.pop(character_id, None)
        else:
            campaign.positions[character_id] = state.position
            campaign.state.positions_parent[character_id] = state.position
            campaign.state.positions[character_id] = state.position
        campaign.state.positions_child[character_id] = None
        campaign.hp[character_id] = state.hp
        campaign.character_states[character_id] = state.character_state

    def _ensure_legacy_maps(self, campaign: Campaign) -> None:
        if not isinstance(campaign.positions, dict):
            campaign.positions = {}
        if not isinstance(campaign.hp, dict):
            campaign.hp = {}
        if not isinstance(campaign.character_states, dict):
            campaign.character_states = {}
        if not isinstance(campaign.state.positions_parent, dict):
            campaign.state.positions_parent = {}
        if not isinstance(campaign.state.positions_child, dict):
            campaign.state.positions_child = {}
        if not isinstance(campaign.state.positions, dict):
            campaign.state.positions = {}

    def _read_position(
        self, campaign: Campaign, character_id: str, actor_position: object
    ) -> Optional[str]:
        for source in (
            campaign.positions,
            campaign.state.positions_parent,
            campaign.state.positions,
        ):
            value = source.get(character_id)
            if isinstance(value, str):
                return value
        if isinstance(actor_position, str):
            return actor_position
        return None

    def _read_hp(self, campaign: Campaign, character_id: str, actor_hp: object) -> int:
        value = campaign.hp.get(character_id)
        if isinstance(value, int):
            return self._normalize_hp(value)
        if isinstance(actor_hp, int):
            return self._normalize_hp(actor_hp)
        return DEFAULT_HP

    def _read_character_state(
        self, campaign: Campaign, character_id: str, actor_character_state: object
    ) -> str:
        value = campaign.character_states.get(character_id)
        if isinstance(value, str):
            return value
        if isinstance(actor_character_state, str):
            return actor_character_state
        return DEFAULT_CHARACTER_STATE

    def _normalize_hp(self, value: int) -> int:
        if value < 0:
            return 0
        return value


class StubCharacterFactStore:
    def get_fact(self, campaign: Campaign, character_id: str) -> CharacterFact:
        actor = campaign.actors.get(character_id)
        meta = actor.meta if actor and isinstance(actor.meta, dict) else {}

        name = meta.get("name")
        role = meta.get("role")
        background = meta.get("background")
        appearance = meta.get("appearance")
        attributes = meta.get("attributes")

        # TODO: replace stub loading with file-backed sources:
        # - storage/characters_library/{id}.json
        # - storage/campaigns/{camp_id}/characters/{id}.fact.json
        return CharacterFact(
            character_id=character_id,
            name=name if isinstance(name, str) else character_id,
            role=role if isinstance(role, str) else "unknown",
            tags=self._read_string_list(meta.get("tags")),
            attributes=attributes if isinstance(attributes, dict) else {},
            background=background if isinstance(background, str) else "",
            appearance=appearance if isinstance(appearance, str) else "",
            personality_tags=self._read_string_list(meta.get("personality_tags")),
        )

    def _read_string_list(self, value: object) -> List[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]


class CharacterFacade:
    def __init__(
        self,
        state_store: CharacterStateStore,
        fact_store: CharacterFactStore,
    ) -> None:
        self.state_store = state_store
        self.fact_store = fact_store

    def get_state(self, campaign: Campaign, character_id: str) -> CharacterState:
        return self.state_store.get_state(campaign, character_id)

    def set_state(
        self, campaign: Campaign, character_id: str, state: CharacterState
    ) -> None:
        self.state_store.set_state(campaign, character_id, state)

    def get_view(self, campaign: Campaign, character_id: str) -> CharacterView:
        fact = self.fact_store.get_fact(campaign, character_id)
        state = self.state_store.get_state(campaign, character_id)
        return CharacterView(
            character_id=fact.character_id,
            name=fact.name,
            role=fact.role,
            tags=list(fact.tags),
            attributes=dict(fact.attributes),
            background=fact.background,
            appearance=fact.appearance,
            personality_tags=list(fact.personality_tags),
            position=state.position,
            hp=state.hp,
            character_state=state.character_state,
        )

    def list_party_views(self, campaign: Campaign) -> List[CharacterView]:
        return [
            self.get_view(campaign, character_id)
            for character_id in campaign.selected.party_character_ids
            if isinstance(character_id, str)
        ]

    def build_state_maps(
        self, campaign: Campaign, character_ids: Optional[Sequence[str]] = None
    ) -> Tuple[
        Dict[str, str],
        Dict[str, str],
        Dict[str, Optional[str]],
        Dict[str, int],
        Dict[str, str],
    ]:
        if character_ids is None:
            character_ids = list(campaign.actors.keys())

        positions: Dict[str, str] = {}
        hp: Dict[str, int] = {}
        character_states: Dict[str, str] = {}
        positions_child: Dict[str, Optional[str]] = {}

        for character_id in character_ids:
            if not isinstance(character_id, str):
                continue
            state = self.get_state(campaign, character_id)
            if state.position is not None:
                positions[character_id] = state.position
            hp[character_id] = state.hp
            character_states[character_id] = state.character_state
            positions_child[character_id] = None

        return positions, dict(positions), positions_child, hp, character_states


def create_character_facade() -> CharacterFacade:
    return CharacterFacade(
        state_store=CampaignCharacterStateStore(),
        fact_store=StubCharacterFactStore(),
    )
