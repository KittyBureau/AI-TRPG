from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from backend.domain.map_models import migrate_map_dict, normalize_map, require_valid_map
from backend.domain.models import Campaign, CampaignSummary, TurnLogEntry
from backend.domain.state_utils import ensure_positions_child, sync_state_positions


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
        sync_state_positions(campaign)
        ensure_positions_child(campaign, campaign.selected.party_character_ids)
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
        sync_state_positions(campaign)
        ensure_positions_child(campaign, campaign.selected.party_character_ids)
        normalize_map(campaign.map)
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
