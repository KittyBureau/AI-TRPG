from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from backend.app.character_fact_generation import (
    CharacterFactBatchWriteResult,
    CharacterFactGenerationRequest,
    CharacterFactGenerationService,
    CharacterFactRequestError,
    CharacterFactValidationError,
)
from backend.domain.character_fact_schema import (
    CharacterFactSchemaError,
    validate_character_fact,
)
from backend.infra.file_repo import FileRepo

MAX_GENERATE_REQUEST_BYTES = 200_000


class CharacterFactNotFoundError(FileNotFoundError):
    pass


class CharacterFactApiService:
    def __init__(
        self,
        repo: FileRepo,
        generation_service: Optional[CharacterFactGenerationService] = None,
    ) -> None:
        self.repo = repo
        self.generation_service = generation_service or CharacterFactGenerationService(repo)

    def generate(
        self,
        campaign_id: str,
        request_payload: Dict[str, Any],
    ) -> CharacterFactBatchWriteResult:
        self._require_campaign(campaign_id)
        payload_size = len(json.dumps(request_payload, ensure_ascii=False).encode("utf-8"))
        if payload_size > MAX_GENERATE_REQUEST_BYTES:
            raise CharacterFactRequestError("request payload is too large.")

        request_id = request_payload.get("request_id")
        if not isinstance(request_id, str) or not request_id.strip():
            request_id = self.generation_service.make_request_id()

        max_count = request_payload.get("max_count")
        if not isinstance(max_count, int):
            max_count = self.generation_service.config.count_max

        request_snapshot = dict(request_payload)
        request_snapshot["request_id"] = request_id
        request_snapshot["campaign_id"] = campaign_id
        request_snapshot["max_count"] = max_count

        request = CharacterFactGenerationRequest(
            campaign_id=campaign_id,
            request_id=request_id,
            language=_read_string(request_payload.get("language"), "zh-CN"),
            tone_style=_read_str_list(request_payload.get("tone_style")),
            tone_vocab_only=_read_bool(request_payload.get("tone_vocab_only"), True),
            allowed_tones=_read_str_list(request_payload.get("allowed_tones")),
            party_context=_read_dict_list(request_payload.get("party_context")),
            constraints=_read_dict(request_payload.get("constraints")),
            count=_read_int(request_payload.get("count"), 3),
            max_count=max_count,
            id_policy=_read_string(request_payload.get("id_policy"), "system"),
            extra_params=request_snapshot,
        )
        return self.generation_service.generate_and_persist(request)

    def list_batches(self, campaign_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        self._require_campaign(campaign_id)
        return self.repo.list_character_fact_batches(campaign_id, limit=limit)

    def get_batch(self, campaign_id: str, request_id: str) -> Dict[str, Any]:
        self._require_campaign(campaign_id)
        payload = self.repo.load_character_fact_batch(campaign_id, request_id)
        if not isinstance(payload, dict):
            raise CharacterFactNotFoundError(
                f"CharacterFact batch not found: campaign={campaign_id}, request_id={request_id}"
            )
        return payload

    def get_fact(self, campaign_id: str, character_id: str) -> Dict[str, Any]:
        self._require_campaign(campaign_id)
        payload = self.repo.load_character_fact_draft(campaign_id, character_id)
        if payload is None:
            payload = self.repo.load_character_fact_from_batches(campaign_id, character_id)
        if payload is None:
            raise CharacterFactNotFoundError(
                f"CharacterFact not found: campaign={campaign_id}, character_id={character_id}"
            )
        try:
            return validate_character_fact(payload)
        except CharacterFactSchemaError as exc:
            raise CharacterFactValidationError(str(exc)) from exc

    def _require_campaign(self, campaign_id: str) -> None:
        try:
            self.repo.get_campaign(campaign_id)
        except FileNotFoundError as exc:
            raise CharacterFactNotFoundError(str(exc)) from exc


def _read_dict(value: object) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _read_dict_list(value: object) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _read_str_list(value: object) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _read_string(value: object, default: str) -> str:
    if not isinstance(value, str):
        return default
    trimmed = value.strip()
    return trimmed or default


def _read_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _read_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    return default
