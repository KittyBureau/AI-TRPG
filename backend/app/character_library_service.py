from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple
from uuid import uuid4

from backend.infra.resource_loader import ResourceLoaderError, load_enabled_template
from backend.infra.file_repo import FileRepo

logger = logging.getLogger(__name__)


class CharacterLibraryNotFoundError(FileNotFoundError):
    pass


class CharacterLibraryValidationError(ValueError):
    pass


class CharacterLibraryDataError(RuntimeError):
    pass


class CharacterLibraryService:
    def __init__(self, repo: FileRepo) -> None:
        self.repo = repo

    def list_facts(self) -> List[Dict[str, Any]]:
        summaries: List[Dict[str, Any]] = []
        for path in self.repo.list_character_library_paths():
            try:
                normalized = self._load_and_normalize_fact_from_path(path)
            except CharacterLibraryDataError as exc:
                logger.warning(
                    "Skip invalid character library entry: %s (%s)",
                    path,
                    exc,
                )
                continue
            summaries.append(
                {
                    "id": normalized["id"],
                    "name": normalized["name"],
                    "summary": normalized["summary"],
                    "tags": list(normalized["tags"]),
                }
            )
        return summaries

    def get_fact(self, character_id: str) -> Dict[str, Any]:
        normalized_id = self._normalize_character_id(character_id)
        path = self.repo.character_library_path(normalized_id)
        if not path.exists():
            raise CharacterLibraryNotFoundError(
                f"Character library fact not found: {normalized_id}"
            )
        try:
            return self._load_and_normalize_fact_from_path(path)
        except CharacterLibraryDataError as exc:
            raise CharacterLibraryDataError(
                f"Character library fact invalid: {normalized_id}"
            ) from exc

    def upsert_fact(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        fact, _ = self.upsert_fact_with_template_usage(payload)
        return fact

    def upsert_fact_with_template_usage(
        self, payload: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if not isinstance(payload, dict):
            raise CharacterLibraryValidationError("request payload must be an object.")

        normalized_payload = dict(payload)
        template_defaults, usage = self._load_character_fact_template_defaults()
        normalized_payload, applied = self._apply_template_defaults(
            normalized_payload, template_defaults
        )
        usage["applied"] = applied

        raw_id = normalized_payload.get("id")
        if isinstance(raw_id, str) and raw_id.strip():
            character_id = self._normalize_character_id(raw_id)
        elif raw_id is None or (isinstance(raw_id, str) and not raw_id.strip()):
            character_id = self._allocate_character_id()
            normalized_payload.pop("id", None)
        else:
            raise CharacterLibraryValidationError("id must be a string when provided.")

        normalized = self._normalize_fact(normalized_payload, expected_id=character_id)
        self.repo.save_character_library_fact(character_id, normalized)
        return normalized, usage

    def _allocate_character_id(self) -> str:
        for _ in range(256):
            candidate = f"ch_{uuid4().hex[:8]}"
            if not self.repo.character_library_path(candidate).exists():
                return candidate
        raise RuntimeError("Failed to allocate character_id.")

    def _normalize_character_id(self, character_id: str) -> str:
        normalized = character_id.strip()
        if not normalized:
            raise CharacterLibraryValidationError("character_id is required.")
        if not _is_storage_safe_id(normalized):
            raise CharacterLibraryValidationError(
                f"invalid character_id: {character_id}"
            )
        return normalized

    def _load_and_normalize_fact_from_path(self, path) -> Dict[str, Any]:
        try:
            expected_id = self._normalize_character_id(path.stem)
        except CharacterLibraryValidationError as exc:
            raise CharacterLibraryDataError("character library filename is invalid.") from exc

        payload = self.repo.load_character_library_fact_by_path(path)
        if payload is None:
            raise CharacterLibraryDataError("character library file is unreadable.")
        try:
            return self._normalize_fact(payload, expected_id=expected_id)
        except CharacterLibraryValidationError as exc:
            raise CharacterLibraryDataError(str(exc)) from exc

    def _normalize_fact(self, payload: Dict[str, Any], *, expected_id: str) -> Dict[str, Any]:
        raw_name = payload.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise CharacterLibraryValidationError("name is required.")

        if "id" in payload:
            raw_id = payload.get("id")
            if not isinstance(raw_id, str) or not raw_id.strip():
                raise CharacterLibraryValidationError("id must be a non-empty string.")
            normalized_payload_id = self._normalize_character_id(raw_id)
            if normalized_payload_id != expected_id:
                raise CharacterLibraryValidationError("id must match path character_id.")

        summary = payload.get("summary", "")
        if summary is None:
            summary = ""
        if not isinstance(summary, str):
            raise CharacterLibraryValidationError("summary must be a string.")

        tags = payload.get("tags", [])
        if tags is None:
            tags = []
        if not isinstance(tags, list) or any(not isinstance(item, str) for item in tags):
            raise CharacterLibraryValidationError("tags must be a list of strings.")

        if "meta" in payload and payload.get("meta") is not None and not isinstance(
            payload.get("meta"), dict
        ):
            raise CharacterLibraryValidationError("meta must be an object when provided.")

        normalized = dict(payload)
        normalized["id"] = expected_id
        normalized["name"] = raw_name.strip()
        normalized["summary"] = summary
        normalized["tags"] = list(tags)
        return normalized

    def _load_character_fact_template_defaults(
        self,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        template_name = "character_fact_stub"
        repo_root = self.repo.storage_root.parent
        try:
            loaded = load_enabled_template(template_name, repo_root=repo_root)
        except ResourceLoaderError:
            return (
                {},
                {
                    "name": template_name,
                    "version": "builtin-v1",
                    "hash": "",
                    "fallback": True,
                },
            )

        content = loaded.content if isinstance(loaded.content, dict) else {}
        defaults: Dict[str, Any] = {}

        summary = content.get("summary")
        defaults["summary"] = summary if isinstance(summary, str) else ""

        tags = content.get("tags")
        if isinstance(tags, list) and all(isinstance(item, str) for item in tags):
            defaults["tags"] = list(tags)
        else:
            defaults["tags"] = []

        meta = content.get("meta")
        defaults["meta"] = dict(meta) if isinstance(meta, dict) else {}

        return (
            defaults,
            {
                "name": loaded.name,
                "version": loaded.version,
                "hash": loaded.source_hash,
                "fallback": False,
            },
        )

    def _apply_template_defaults(
        self, payload: Dict[str, Any], defaults: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        patched = dict(payload)
        applied = False

        if ("summary" not in patched or patched.get("summary") is None) and "summary" in defaults:
            patched["summary"] = defaults["summary"]
            applied = True
        if ("tags" not in patched or patched.get("tags") is None) and "tags" in defaults:
            patched["tags"] = defaults["tags"]
            applied = True
        if ("meta" not in patched or patched.get("meta") is None) and "meta" in defaults:
            patched["meta"] = defaults["meta"]
            applied = True

        return patched, applied


def _is_storage_safe_id(value: str) -> bool:
    for ch in value:
        if ch.isalnum() or ch in {"_", "-"}:
            continue
        return False
    return True


__all__ = [
    "CharacterLibraryDataError",
    "CharacterLibraryNotFoundError",
    "CharacterLibraryService",
    "CharacterLibraryValidationError",
]
