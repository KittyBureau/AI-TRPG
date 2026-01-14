from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.settings_service import SettingsService
from backend.domain.models import SettingsSnapshot
from backend.infra.file_repo import FileRepo

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _service() -> SettingsService:
    storage_root = Path.cwd() / "storage"
    repo = FileRepo(storage_root)
    return SettingsService(repo)


class SettingDefinitionResponse(BaseModel):
    key: str
    type: str
    default: Any
    scope: str
    validation: Dict[str, Any]
    ui_hint: str
    effect_tags: List[str]


class SettingsSchemaResponse(BaseModel):
    definitions: List[SettingDefinitionResponse]
    snapshot: SettingsSnapshot


class SettingsApplyRequest(BaseModel):
    campaign_id: str
    patch: Dict[str, Any] = Field(default_factory=dict)


class SettingsApplyResponse(BaseModel):
    snapshot: SettingsSnapshot
    change_summary: List[str] = Field(default_factory=list)


@router.get("/schema", response_model=SettingsSchemaResponse)
def get_schema(campaign_id: str = Query(...)) -> SettingsSchemaResponse:
    service = _service()
    try:
        definitions, snapshot = service.get_schema(campaign_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SettingsSchemaResponse(
        definitions=[
            SettingDefinitionResponse(**definition.model_dump())
            if hasattr(definition, "model_dump")
            else SettingDefinitionResponse(**definition.dict())
            for definition in definitions
        ],
        snapshot=snapshot,
    )


@router.post("/apply", response_model=SettingsApplyResponse)
def apply_settings(request: SettingsApplyRequest) -> SettingsApplyResponse:
    service = _service()
    try:
        snapshot, changed_keys = service.apply_patch(
            request.campaign_id, request.patch
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SettingsApplyResponse(snapshot=snapshot, change_summary=changed_keys)
