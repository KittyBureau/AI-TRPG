from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from backend.app.character_fact_api_service import (
    CharacterFactApiService,
    CharacterFactNotFoundError,
)
from backend.app.character_fact_generation import (
    CharacterFactConflictError,
    CharacterFactRequestError,
    CharacterFactValidationError,
)
from backend.infra.file_repo import FileRepo

router = APIRouter(prefix="/campaigns", tags=["characters"])


def _service() -> CharacterFactApiService:
    storage_root = Path.cwd() / "storage"
    repo = FileRepo(storage_root)
    return CharacterFactApiService(repo)


class CharacterGenerateConstraints(BaseModel):
    allowed_roles: List[str] = Field(default_factory=list)
    style_notes: str | None = None


class CharacterGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    language: str = "zh-CN"
    tone_style: List[str] = Field(default_factory=list)
    tone_vocab_only: bool = True
    allowed_tones: List[str] = Field(default_factory=list)
    party_context: List[Dict[str, Any]] = Field(default_factory=list)
    constraints: CharacterGenerateConstraints = Field(
        default_factory=CharacterGenerateConstraints
    )
    count: int = 3
    max_count: int | None = None
    request_id: str | None = None
    id_policy: str = "system"

    def to_payload(self) -> Dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump()
        return self.dict()


class CharacterGenerateRefsResponse(BaseModel):
    campaign_id: str
    request_id: str
    batch_path: str
    individual_paths: List[str] = Field(default_factory=list)
    count_requested: int
    count_generated: int
    warnings: List[str] = Field(default_factory=list)


class CharacterBatchSummary(BaseModel):
    request_id: str
    utc_ts: str
    path: str
    count: int


class CharacterBatchListResponse(BaseModel):
    batches: List[CharacterBatchSummary] = Field(default_factory=list)


@router.post(
    "/{campaign_id}/characters/generate",
    response_model=CharacterGenerateRefsResponse,
)
def generate_character_facts(
    campaign_id: str,
    request: CharacterGenerateRequest,
) -> CharacterGenerateRefsResponse:
    service = _service()
    try:
        result = service.generate(campaign_id, request.to_payload())
    except CharacterFactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CharacterFactConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CharacterFactRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CharacterFactValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Character generation failed.") from exc

    return CharacterGenerateRefsResponse(
        campaign_id=result.campaign_id,
        request_id=result.request_id,
        batch_path=result.batch_path,
        individual_paths=result.individual_paths,
        count_requested=result.count_requested,
        count_generated=result.count_generated,
        warnings=result.warnings,
    )


@router.get(
    "/{campaign_id}/characters/generated/batches",
    response_model=CharacterBatchListResponse,
)
def list_generated_batches(
    campaign_id: str,
    limit: int = Query(20, ge=1, le=200),
) -> CharacterBatchListResponse:
    service = _service()
    try:
        batches = service.list_batches(campaign_id, limit=limit)
    except CharacterFactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return CharacterBatchListResponse(
        batches=[CharacterBatchSummary(**item) for item in batches]
    )


@router.get("/{campaign_id}/characters/generated/batches/{request_id}")
def get_generated_batch(campaign_id: str, request_id: str) -> Dict[str, Any]:
    service = _service()
    try:
        return service.get_batch(campaign_id, request_id)
    except CharacterFactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{campaign_id}/characters/facts/{character_id}")
def get_character_fact(campaign_id: str, character_id: str) -> Dict[str, Any]:
    service = _service()
    try:
        return service.get_fact(campaign_id, character_id)
    except CharacterFactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CharacterFactValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
