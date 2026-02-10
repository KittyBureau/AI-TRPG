from __future__ import annotations

from pathlib import Path
from typing import Optional

from backend.domain.character_access import (
    CampaignCharacterStateStore,
    CharacterFacade,
)
from backend.infra.character_fact_store import GeneratedCharacterFactStore


def create_runtime_character_facade(
    storage_root: Optional[Path] = None,
) -> CharacterFacade:
    return CharacterFacade(
        state_store=CampaignCharacterStateStore(),
        fact_store=GeneratedCharacterFactStore(storage_root=storage_root),
    )
