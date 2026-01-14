from __future__ import annotations

from typing import Any, Dict, List, Tuple

from backend.domain.models import SettingsSnapshot
from backend.domain.settings import SettingDefinition, apply_settings_patch, get_definitions
from backend.infra.file_repo import FileRepo


class SettingsService:
    def __init__(self, repo: FileRepo) -> None:
        self.repo = repo

    def get_schema(self, campaign_id: str) -> Tuple[List[SettingDefinition], SettingsSnapshot]:
        campaign = self.repo.get_campaign(campaign_id)
        return get_definitions(), campaign.settings_snapshot

    def apply_patch(
        self, campaign_id: str, patch: Dict[str, Any]
    ) -> Tuple[SettingsSnapshot, List[str]]:
        campaign = self.repo.get_campaign(campaign_id)
        updated_snapshot, changed_keys = apply_settings_patch(
            campaign.settings_snapshot, patch
        )
        if changed_keys:
            campaign.settings_snapshot = updated_snapshot
            campaign.settings_revision += 1
            self.repo.save_campaign(campaign)
        return updated_snapshot, changed_keys
