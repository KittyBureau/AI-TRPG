from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.domain.map_models import migrate_map_dict, normalize_map, require_valid_map
from backend.domain.models import ActorState, Campaign, CampaignSummary, TurnLogEntry
from backend.domain.state_utils import (
    DEFAULT_CHARACTER_STATE,
    DEFAULT_HP,
    ensure_actor,
    validate_actors_state,
)


def _model_to_dict(model: object) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    if hasattr(model, "dict"):
        return model.dict()  # type: ignore[no-any-return]
    raise TypeError("Unsupported model type")


def _model_from_dict(model_cls: object, data: Dict[str, Any]) -> object:
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)  # type: ignore[no-any-return]
    if hasattr(model_cls, "parse_obj"):
        return model_cls.parse_obj(data)  # type: ignore[no-any-return]
    raise TypeError("Unsupported model type")


def _read_dict(value: object) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _read_str_map(value: object) -> Dict[str, str]:
    return {
        key: val
        for key, val in _read_dict(value).items()
        if isinstance(key, str) and isinstance(val, str)
    }


def _collect_actor_ids(data: Dict[str, Any]) -> List[str]:
    actor_ids = set()
    selected = _read_dict(data.get("selected"))
    party_ids = selected.get("party_character_ids")
    if isinstance(party_ids, list):
        actor_ids.update({item for item in party_ids if isinstance(item, str)})
    active_actor_id = selected.get("active_actor_id")
    if isinstance(active_actor_id, str):
        actor_ids.add(active_actor_id)
    for field in ("positions", "hp", "character_states"):
        actor_ids.update(_read_dict(data.get(field)).keys())
    state = _read_dict(data.get("state"))
    actor_ids.update(_read_dict(state.get("positions_parent")).keys())
    actor_ids.update(_read_dict(state.get("positions")).keys())
    return sorted({actor_id for actor_id in actor_ids if isinstance(actor_id, str)})


def _get_legacy_position(
    actor_id: str,
    positions: Dict[str, str],
    positions_parent: Dict[str, str],
    positions_state: Dict[str, str],
) -> Optional[str]:
    if actor_id in positions:
        return positions[actor_id]
    if actor_id in positions_parent:
        return positions_parent[actor_id]
    if actor_id in positions_state:
        return positions_state[actor_id]
    return None


def _migrate_actors_if_needed(campaign: Campaign, data: Dict[str, Any]) -> bool:
    actors_raw = data.get("actors")
    actors_present = isinstance(actors_raw, dict) and bool(actors_raw)
    legacy_positions = _read_str_map(data.get("positions"))
    legacy_hp = _read_dict(data.get("hp"))
    legacy_states = _read_dict(data.get("character_states"))
    state = _read_dict(data.get("state"))
    legacy_positions_parent = _read_str_map(state.get("positions_parent"))
    legacy_positions_state = _read_str_map(state.get("positions"))
    legacy_present = any(
        [legacy_positions, legacy_hp, legacy_states, legacy_positions_parent, legacy_positions_state]
    )

    if actors_present:
        if legacy_present:
            campaign.positions = {}
            campaign.hp = {}
            campaign.character_states = {}
            campaign.state.positions = {}
            campaign.state.positions_parent = {}
            campaign.state.positions_child = {}
            return True
        return False

    actor_ids = _collect_actor_ids(data)
    actors: Dict[str, ActorState] = {}
    for actor_id in actor_ids:
        position = _get_legacy_position(
            actor_id, legacy_positions, legacy_positions_parent, legacy_positions_state
        )
        hp_value = legacy_hp.get(actor_id, DEFAULT_HP)
        if not isinstance(hp_value, int):
            hp_value = DEFAULT_HP
        state_value = legacy_states.get(actor_id, DEFAULT_CHARACTER_STATE)
        if not isinstance(state_value, str):
            state_value = DEFAULT_CHARACTER_STATE
        actors[actor_id] = ActorState(
            position=position, hp=hp_value, character_state=state_value, meta={}
        )

    campaign.actors = actors
    campaign.positions = {}
    campaign.hp = {}
    campaign.character_states = {}
    campaign.state.positions = {}
    campaign.state.positions_parent = {}
    campaign.state.positions_child = {}
    return True


class FileRepo:
    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root
        self.campaigns_root = storage_root / "campaigns"
        self.campaigns_root.mkdir(parents=True, exist_ok=True)

    def _campaign_dir(self, campaign_id: str) -> Path:
        return self.campaigns_root / campaign_id

    def _campaign_path(self, campaign_id: str) -> Path:
        return self._campaign_dir(campaign_id) / "campaign.json"

    def _turn_log_path(self, campaign_id: str) -> Path:
        return self._campaign_dir(campaign_id) / "turn_log.jsonl"

    def next_campaign_id(self) -> str:
        max_id = 0
        for path in self.campaigns_root.glob("camp_*"):
            suffix = path.name.replace("camp_", "")
            if suffix.isdigit():
                max_id = max(max_id, int(suffix))
        return f"camp_{max_id + 1:04d}"

    def next_turn_id(self, campaign_id: str) -> str:
        path = self._turn_log_path(campaign_id)
        if not path.exists():
            return "turn_0001"
        count = 0
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    count += 1
        return f"turn_{count + 1:04d}"

    def create_campaign(self, campaign: Campaign) -> None:
        campaign_dir = self._campaign_dir(campaign.id)
        campaign_dir.mkdir(parents=True, exist_ok=True)
        path = self._campaign_path(campaign.id)
        if path.exists():
            raise FileExistsError(f"Campaign already exists: {campaign.id}")
        self.save_campaign(campaign)

    def save_campaign(self, campaign: Campaign) -> None:
        path = self._campaign_path(campaign.id)
        validate_actors_state(campaign, campaign.map)
        campaign.positions = {}
        campaign.hp = {}
        campaign.character_states = {}
        campaign.state.positions = {}
        campaign.state.positions_parent = {}
        campaign.state.positions_child = {}
        require_valid_map(campaign.map)
        normalize_map(campaign.map)
        data = _model_to_dict(campaign)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_campaign(self, campaign_id: str) -> Campaign:
        path = self._campaign_path(campaign_id)
        if not path.exists():
            raise FileNotFoundError(f"Campaign not found: {campaign_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        map_data = data.get("map")
        if isinstance(map_data, dict):
            migrate_map_dict(map_data)
        campaign = _model_from_dict(Campaign, data)
        updated = _migrate_actors_if_needed(campaign, data)
        for actor_id in campaign.selected.party_character_ids:
            if actor_id not in campaign.actors:
                ensure_actor(campaign, actor_id)
                updated = True
        if campaign.selected.active_actor_id not in campaign.actors:
            ensure_actor(campaign, campaign.selected.active_actor_id)
            updated = True
        if validate_actors_state(campaign, campaign.map):
            updated = True
        normalize_map(campaign.map)
        if updated:
            self.save_campaign(campaign)
        return campaign

    def list_campaigns(self) -> List[CampaignSummary]:
        summaries: List[CampaignSummary] = []
        for path in self.campaigns_root.glob("camp_*"):
            campaign_path = path / "campaign.json"
            if not campaign_path.exists():
                continue
            data = json.loads(campaign_path.read_text(encoding="utf-8"))
            summaries.append(
                CampaignSummary(
                    id=data["id"],
                    world_id=data["selected"]["world_id"],
                    active_actor_id=data["selected"]["active_actor_id"],
                )
            )
        return summaries

    def update_active_actor(self, campaign: Campaign, actor_id: str) -> Campaign:
        campaign.selected.active_actor_id = actor_id
        self.save_campaign(campaign)
        return campaign

    def append_turn_log(self, campaign_id: str, entry: TurnLogEntry) -> None:
        path = self._turn_log_path(campaign_id)
        data = _model_to_dict(entry)
        line = json.dumps(data)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
