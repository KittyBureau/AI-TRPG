from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.domain.world_models import WorldGenerator
from backend.infra.file_repo import FileRepo

router = APIRouter(prefix="/campaigns", tags=["world"])


def _repo() -> FileRepo:
    storage_root = Path.cwd() / "storage"
    return FileRepo(storage_root)


class WorldResponse(BaseModel):
    world_id: str
    name: str
    seed: int | str
    generator: WorldGenerator
    schema_version: str
    created_at: str
    updated_at: str


@router.get("/{campaign_id}/world", response_model=WorldResponse)
def get_world_for_campaign(campaign_id: str) -> WorldResponse:
    repo = _repo()
    try:
        campaign = repo.get_campaign(campaign_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    world_id = campaign.selected.world_id.strip() if campaign.selected.world_id else ""
    if not world_id:
        raise HTTPException(
            status_code=409,
            detail=f"campaign has no world_id: {campaign_id}",
        )

    try:
        world = repo.get_or_create_world_stub(world_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if hasattr(world, "model_dump"):
        return WorldResponse(**world.model_dump())
    return WorldResponse(**world.dict())
