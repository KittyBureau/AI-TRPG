from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.world_presets import list_world_presets
from backend.app.world_service import generate_world_resource
from backend.domain.world_models import WorldGenerator
from backend.infra.file_repo import FileRepo

router = APIRouter(tags=["world"])


def _repo() -> FileRepo:
    storage_root = Path.cwd() / "storage"
    return FileRepo(storage_root)


class WorldResponse(BaseModel):
    world_id: str
    name: str
    seed: int | str
    world_description: str
    objective: str
    start_area: str
    generator: WorldGenerator
    schema_version: str
    created_at: str
    updated_at: str


class WorldSummaryGeneratorResponse(BaseModel):
    id: str = ""


class WorldSummaryScenarioResponse(BaseModel):
    label: str = ""
    template_id: str = ""
    area_count: int | None = None
    difficulty: str = ""


class WorldSummaryResponse(BaseModel):
    world_id: str
    name: str
    generator: WorldSummaryGeneratorResponse
    scenario: WorldSummaryScenarioResponse | None = None
    updated_at: str


class GenerateWorldRequest(BaseModel):
    world_id: str
    name: str | None = None
    generator_id: str | None = None
    generator_params: dict[str, Any] | None = None


class GenerateWorldResponse(WorldResponse):
    created: bool
    normalized: bool


@router.get("/worlds/list", response_model=list[WorldSummaryResponse])
def list_worlds() -> list[WorldSummaryResponse]:
    repo = _repo()
    worlds_by_id = {world.world_id: world for world in repo.list_worlds()}
    for world in list_world_presets():
        worlds_by_id.setdefault(world.world_id, world)
    worlds = sorted(
        worlds_by_id.values(),
        key=lambda world: (world.updated_at, world.world_id),
        reverse=True,
    )
    return [
        WorldSummaryResponse(
            world_id=world.world_id,
            name=world.name,
            generator=WorldSummaryGeneratorResponse(id=world.generator.id if world.generator else ""),
            scenario=_build_scenario_summary(world),
            updated_at=world.updated_at,
        )
        for world in worlds
    ]


def _build_scenario_summary(world) -> WorldSummaryScenarioResponse | None:
    generator = getattr(world, "generator", None)
    if generator is None or getattr(generator, "id", "").strip() != "playable_scenario_v0":
        return None
    params = generator.params if isinstance(generator.params, dict) else {}
    template_id = str(params.get("template_id", "")).strip()
    if template_id != "key_gate_scenario":
        return None
    area_count = params.get("area_count")
    difficulty = str(params.get("difficulty", "")).strip()
    return WorldSummaryScenarioResponse(
        label="Key Gate Scenario",
        template_id=template_id,
        area_count=area_count if isinstance(area_count, int) else None,
        difficulty=difficulty,
    )


@router.post("/worlds/generate", response_model=GenerateWorldResponse)
def generate_world_standalone(request: GenerateWorldRequest) -> GenerateWorldResponse:
    repo = _repo()
    try:
        result = generate_world_resource(
            world_id=request.world_id,
            name=request.name,
            generator_id=request.generator_id,
            generator_params=request.generator_params,
            repo=repo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GenerateWorldResponse(**result)


@router.get("/campaigns/{campaign_id}/world", response_model=WorldResponse)
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
        world = generate_world_resource(world_id=world_id, repo=repo)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return WorldResponse(
        world_id=world["world_id"],
        name=world["name"],
        seed=world["seed"],
        world_description=world["world_description"],
        objective=world["objective"],
        start_area=world["start_area"],
        generator=world["generator"],
        schema_version=world["schema_version"],
        created_at=world["created_at"],
        updated_at=world["updated_at"],
    )
