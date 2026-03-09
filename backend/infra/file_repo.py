from __future__ import annotations

import json
import re
from datetime import datetime, timezone
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
from backend.domain.world_models import (
    World,
    build_world_stub,
    normalize_world,
    require_valid_world,
)

BATCH_FILE_PATTERN = re.compile(r"^batch_(\d{8}T\d{6}Z)_(.+)\.json$")


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
        self.characters_library_root = storage_root / "characters_library"
        self.worlds_root = storage_root / "worlds"
        self.campaigns_root.mkdir(parents=True, exist_ok=True)
        self.characters_library_root.mkdir(parents=True, exist_ok=True)
        self.worlds_root.mkdir(parents=True, exist_ok=True)

    def _campaign_dir(self, campaign_id: str) -> Path:
        return self.campaigns_root / campaign_id

    def _campaign_path(self, campaign_id: str) -> Path:
        return self._campaign_dir(campaign_id) / "campaign.json"

    def _turn_log_path(self, campaign_id: str) -> Path:
        return self._campaign_dir(campaign_id) / "turn_log.jsonl"

    def _generated_characters_dir(self, campaign_id: str) -> Path:
        return self._campaign_dir(campaign_id) / "characters" / "generated"

    def _world_dir(self, world_id: str) -> Path:
        return self.worlds_root / world_id

    def world_path(self, world_id: str) -> Path:
        return self._world_dir(world_id) / "world.json"

    def _normalize_storage_id(self, value: str, *, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{label} is required")
        if re.fullmatch(r"[a-zA-Z0-9_-]+", normalized) is None:
            raise ValueError(f"invalid {label}: {value}")
        return normalized

    def _character_library_path(self, character_id: str) -> Path:
        normalized_character_id = self._normalize_storage_id(
            character_id, label="character_id"
        )
        return self.characters_library_root / f"{normalized_character_id}.json"

    def character_library_path(self, character_id: str) -> Path:
        return self._character_library_path(character_id)

    def _sanitize_request_id(self, request_id: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", request_id.strip())
        return cleaned or "req"

    def _sanitize_character_file_id(self, character_id: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", character_id.strip())
        return cleaned or "character"

    def to_storage_relative_path(self, path: Path) -> str:
        try:
            relative = path.relative_to(self.storage_root)
            if self.storage_root.name == "storage":
                return str(Path("storage") / relative).replace("\\", "/")
            return str(relative).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    def list_character_library_paths(self) -> List[Path]:
        return sorted(
            self.characters_library_root.glob("*.json"),
            key=lambda item: item.stem,
        )

    def load_character_library_fact(self, character_id: str) -> Optional[Dict[str, Any]]:
        path = self._character_library_path(character_id)
        if not path.exists():
            return None
        return self.load_character_library_fact_by_path(path)

    def load_character_library_fact_by_path(
        self,
        path: Path,
    ) -> Optional[Dict[str, Any]]:
        payload = self._read_json_file(path)
        if isinstance(payload, dict):
            return payload
        return None

    def save_character_library_fact(
        self,
        character_id: str,
        payload: Dict[str, Any],
    ) -> Path:
        path = self._character_library_path(character_id)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def _read_json_file(self, path: Path) -> Optional[Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _extract_batch_parts(self, path: Path) -> tuple[Optional[str], Optional[str]]:
        match = BATCH_FILE_PATTERN.match(path.name)
        if not match:
            return None, None
        return match.group(1), match.group(2)

    def get_world(self, world_id: str) -> Optional[World]:
        normalized_world_id = world_id.strip()
        if not normalized_world_id:
            return None
        path = self.world_path(normalized_world_id)
        if not path.exists():
            return None
        payload = self._read_json_file(path)
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid world JSON: {path}")
        world = _model_from_dict(World, payload)
        require_valid_world(world)
        normalize_world(world)
        return world

    def save_world(self, world: World) -> None:
        require_valid_world(world)
        normalize_world(world)
        world_dir = self._world_dir(world.world_id)
        world_dir.mkdir(parents=True, exist_ok=True)
        path = self.world_path(world.world_id)
        payload = _model_to_dict(world)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get_or_create_world_stub(
        self,
        world_id: str,
        *,
        seed_source: str = "world_id_hash",
        generator_default: str = "stub",
    ) -> World:
        normalized_world_id = world_id.strip()
        if not normalized_world_id:
            raise ValueError("world_id is required")

        existing = self.get_world(normalized_world_id)
        if existing is not None:
            return existing

        world = build_world_stub(
            normalized_world_id,
            seed_source=seed_source,
            generator_default=generator_default,
        )
        world_dir = self._world_dir(normalized_world_id)
        world_dir.mkdir(parents=True, exist_ok=True)
        path = self.world_path(normalized_world_id)
        payload = _model_to_dict(world)

        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            return world
        except FileExistsError:
            # Concurrent request won the race; read the winner.
            existing_after_race = self.get_world(normalized_world_id)
            if existing_after_race is None:
                raise
            return existing_after_race

    def find_character_fact_batch_path(
        self,
        campaign_id: str,
        request_id: str,
    ) -> Optional[Path]:
        generated_dir = self._generated_characters_dir(campaign_id)
        if not generated_dir.exists():
            return None

        safe_request_id = self._sanitize_request_id(request_id)
        unreadable_candidate: Optional[Path] = None

        for path in sorted(generated_dir.glob("batch_*.json"), reverse=True):
            payload = self._read_json_file(path)
            if isinstance(payload, dict):
                stored_request_id = payload.get("request_id")
                if isinstance(stored_request_id, str) and stored_request_id == request_id:
                    return path
            _, suffix = self._extract_batch_parts(path)
            if suffix == safe_request_id and not isinstance(payload, dict):
                unreadable_candidate = path

        return unreadable_candidate

    def save_character_fact_batch(
        self,
        campaign_id: str,
        request_id: str,
        payload: Dict[str, Any],
        utc_ts: Optional[str] = None,
    ) -> Path:
        generated_dir = self._generated_characters_dir(campaign_id)
        generated_dir.mkdir(parents=True, exist_ok=True)
        existing = self.find_character_fact_batch_path(campaign_id, request_id)
        if existing is not None:
            raise FileExistsError(
                f"Character batch already exists for request_id={request_id}"
            )
        timestamp = utc_ts or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_request_id = self._sanitize_request_id(request_id)
        path = generated_dir / f"batch_{timestamp}_{safe_request_id}.json"
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return path

    def save_character_fact_draft(
        self,
        campaign_id: str,
        character_file_id: str,
        payload: Dict[str, Any],
    ) -> Path:
        generated_dir = self._generated_characters_dir(campaign_id)
        generated_dir.mkdir(parents=True, exist_ok=True)
        safe_character_id = self._sanitize_character_file_id(character_file_id)
        path = generated_dir / f"{safe_character_id}.fact.draft.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def character_fact_draft_path(self, campaign_id: str, character_id: str) -> Path:
        safe_character_id = self._sanitize_character_file_id(character_id)
        return self._generated_characters_dir(campaign_id) / (
            f"{safe_character_id}.fact.draft.json"
        )

    def character_fact_acceptance_path(self, campaign_id: str, character_id: str) -> Path:
        safe_character_id = self._sanitize_character_file_id(character_id)
        return self._generated_characters_dir(campaign_id) / (
            f"{safe_character_id}.fact.accepted.json"
        )

    def save_character_fact_acceptance(
        self,
        campaign_id: str,
        character_id: str,
        payload: Dict[str, Any],
    ) -> Path:
        generated_dir = self._generated_characters_dir(campaign_id)
        generated_dir.mkdir(parents=True, exist_ok=True)
        path = self.character_fact_acceptance_path(campaign_id, character_id)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def load_character_fact_acceptance(
        self,
        campaign_id: str,
        character_id: str,
    ) -> Optional[Dict[str, Any]]:
        path = self.character_fact_acceptance_path(campaign_id, character_id)
        if not path.exists():
            return None
        payload = self._read_json_file(path)
        if isinstance(payload, dict):
            return payload
        return None

    def load_character_fact_draft(
        self,
        campaign_id: str,
        character_id: str,
    ) -> Optional[Dict[str, Any]]:
        path = self.character_fact_draft_path(campaign_id, character_id)
        if not path.exists():
            return None
        data = self._read_json_file(path)
        if isinstance(data, dict):
            return data
        return None

    def load_character_fact_batch(
        self,
        campaign_id: str,
        request_id: str,
    ) -> Optional[Dict[str, Any]]:
        path = self.find_character_fact_batch_path(campaign_id, request_id)
        if path is None:
            return None
        payload = self._read_json_file(path)
        if isinstance(payload, dict):
            return payload
        return None

    def load_character_fact_from_batches(
        self,
        campaign_id: str,
        character_id: str,
    ) -> Optional[Dict[str, Any]]:
        generated_dir = self._generated_characters_dir(campaign_id)
        if not generated_dir.exists():
            return None
        batch_paths = sorted(generated_dir.glob("batch_*.json"), reverse=True)
        for path in batch_paths:
            payload = self._read_json_file(path)
            if not isinstance(payload, dict):
                continue
            items = payload.get("items")
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("character_id") == character_id:
                    return item
        return None

    def character_fact_id_exists(self, campaign_id: str, character_id: str) -> bool:
        if self.load_character_fact_draft(campaign_id, character_id) is not None:
            return True
        return self.load_character_fact_from_batches(campaign_id, character_id) is not None

    def list_character_fact_batches(
        self,
        campaign_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        generated_dir = self._generated_characters_dir(campaign_id)
        if not generated_dir.exists():
            return []
        capped_limit = max(1, min(limit, 200))
        summaries: List[Dict[str, Any]] = []
        for path in sorted(generated_dir.glob("batch_*.json"), reverse=True):
            payload = self._read_json_file(path)
            utc_ts, request_suffix = self._extract_batch_parts(path)
            request_id = request_suffix or ""
            count = 0
            if isinstance(payload, dict):
                raw_request_id = payload.get("request_id")
                if isinstance(raw_request_id, str) and raw_request_id.strip():
                    request_id = raw_request_id
                raw_utc_ts = payload.get("utc_ts")
                if isinstance(raw_utc_ts, str) and raw_utc_ts.strip():
                    utc_ts = raw_utc_ts
                items = payload.get("items")
                if isinstance(items, list):
                    count = len(items)
            summaries.append(
                {
                    "request_id": request_id,
                    "utc_ts": utc_ts or "",
                    "path": self.to_storage_relative_path(path),
                    "count": count,
                }
            )
            if len(summaries) >= capped_limit:
                break
        return summaries

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
        if "inventory_add" not in campaign.allowlist:
            campaign.allowlist.append("inventory_add")
            updated = True
        if "scene_action" not in campaign.allowlist:
            campaign.allowlist.append("scene_action")
            updated = True
        if not isinstance(campaign.entities, dict):
            campaign.entities = {}
            updated = True
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

    def read_recent_turn_log_rows(
        self, campaign_id: str, limit: int = 3
    ) -> List[Dict[str, Any]]:
        path = self._turn_log_path(campaign_id)
        if not path.exists():
            return []
        capped = max(1, min(limit, 200))
        rows: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
        for line in reversed(lines):
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
            if len(rows) >= capped:
                break
        return rows
