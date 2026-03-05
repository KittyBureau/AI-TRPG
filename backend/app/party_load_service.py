from __future__ import annotations

from typing import Any, Dict

from backend.app.character_library_service import (
    CharacterLibraryNotFoundError,
    CharacterLibraryService,
)
from backend.domain.state_utils import ensure_actor
from backend.infra.file_repo import FileRepo


class PartyLoadService:
    def __init__(
        self,
        repo: FileRepo,
        character_library_service: CharacterLibraryService | None = None,
    ) -> None:
        self.repo = repo
        self.character_library_service = character_library_service or CharacterLibraryService(
            repo
        )

    def load_character_to_campaign(
        self,
        campaign_id: str,
        character_id: str,
        *,
        set_active_if_empty: bool = True,
    ) -> Dict[str, Any]:
        fact = self.character_library_service.get_fact(character_id)
        resolved_character_id = fact["id"]
        campaign = self.repo.get_campaign(campaign_id)

        actor = ensure_actor(campaign, resolved_character_id)
        if not isinstance(actor.meta, dict):
            actor.meta = {}
        actor.meta["profile"] = dict(fact)
        actor.meta["character_id"] = resolved_character_id

        if not isinstance(campaign.selected.party_character_ids, list):
            campaign.selected.party_character_ids = []
        if resolved_character_id not in campaign.selected.party_character_ids:
            campaign.selected.party_character_ids.append(resolved_character_id)

        active_actor_id = campaign.selected.active_actor_id
        if set_active_if_empty and (
            not isinstance(active_actor_id, str) or not active_actor_id.strip()
        ):
            campaign.selected.active_actor_id = resolved_character_id

        self.repo.save_campaign(campaign)
        return {
            "ok": True,
            "campaign_id": campaign.id,
            "character_id": resolved_character_id,
            "party_character_ids": list(campaign.selected.party_character_ids),
            "active_actor_id": campaign.selected.active_actor_id,
        }


__all__ = ["PartyLoadService", "CharacterLibraryNotFoundError"]
