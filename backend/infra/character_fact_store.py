from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from backend.domain.character_access import (
    CharacterFact,
    CharacterFactStore,
    StubCharacterFactStore,
)
from backend.domain.models import Campaign
from backend.infra.file_repo import FileRepo


class GeneratedCharacterFactStore(CharacterFactStore):
    def __init__(
        self,
        storage_root: Optional[Path] = None,
        fallback_store: Optional[CharacterFactStore] = None,
    ) -> None:
        root = storage_root or Path("storage")
        self.repo = FileRepo(root)
        self.fallback_store = fallback_store or StubCharacterFactStore()

    def get_fact(self, campaign: Campaign, character_id: str) -> CharacterFact:
        try:
            payload = self.repo.load_character_fact_draft(campaign.id, character_id)
            if payload is None:
                payload = self.repo.load_character_fact_from_batches(
                    campaign.id, character_id
                )
            fact = self._to_character_fact(payload, character_id)
            if fact is not None:
                return fact
        except Exception:
            pass
        return self.fallback_store.get_fact(campaign, character_id)

    def _to_character_fact(
        self,
        payload: Optional[Dict[str, Any]],
        character_id: str,
    ) -> Optional[CharacterFact]:
        if not isinstance(payload, dict):
            return None
        resolved_id = payload.get("character_id")
        if not isinstance(resolved_id, str) or not resolved_id.strip():
            resolved_id = character_id
        name = payload.get("name")
        role = payload.get("role")
        if not isinstance(name, str) or not name.strip():
            return None
        if not isinstance(role, str) or not role.strip():
            return None
        attributes = payload.get("attributes")
        if not isinstance(attributes, dict):
            attributes = {}
        return CharacterFact(
            character_id=resolved_id,
            name=name.strip(),
            role=role.strip(),
            tags=self._read_string_list(payload.get("tags")),
            attributes=attributes,
            background=self._read_string(payload.get("background")),
            appearance=self._read_string(payload.get("appearance")),
            personality_tags=self._read_string_list(payload.get("personality_tags")),
            meta=self._read_meta(payload.get("meta")),
        )

    def _read_string(self, value: object) -> str:
        if not isinstance(value, str):
            return ""
        return value

    def _read_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]

    def _read_meta(self, value: object) -> Dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        hooks = self._read_string_list(value.get("hooks"))
        source = self._read_string(value.get("source"))
        language = self._read_string(value.get("language"))
        normalized: Dict[str, Any] = {}
        if hooks:
            normalized["hooks"] = hooks
        if language:
            normalized["language"] = language
        if source:
            normalized["source"] = source
        return normalized
