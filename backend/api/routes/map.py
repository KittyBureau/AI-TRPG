from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.infra.file_repo import FileRepo

router = APIRouter(prefix="/api/map", tags=["map"])


def _repo() -> FileRepo:
    storage_root = Path.cwd() / "storage"
    return FileRepo(storage_root)


class MapAreaView(BaseModel):
    id: str
    name: str


class MapViewResponse(BaseModel):
    campaign_id: str
    active_actor_id: str
    current_area: MapAreaView
    reachable_areas: List[MapAreaView]


@router.get("/view", response_model=MapViewResponse)
def view_map(
    campaign_id: str = Query(...),
    actor_id: Optional[str] = Query(None),
) -> MapViewResponse:
    repo = _repo()
    try:
        campaign = repo.get_campaign(campaign_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    active_actor_id = actor_id or campaign.selected.active_actor_id
    area_id = campaign.positions.get(active_actor_id)
    if not area_id:
        area_id = campaign.state.positions_parent.get(active_actor_id)
    if not area_id:
        raise HTTPException(
            status_code=400,
            detail=f"Actor has no position: {active_actor_id}",
        )

    current_area = campaign.map.areas.get(area_id)
    if not current_area:
        raise HTTPException(
            status_code=404,
            detail=f"Area not found: {area_id}",
        )

    reachable_areas: List[MapAreaView] = []
    for target_id in current_area.reachable_area_ids:
        target_area = campaign.map.areas.get(target_id)
        if not target_area:
            continue
        reachable_areas.append(
            MapAreaView(id=target_area.id, name=target_area.name)
        )

    return MapViewResponse(
        campaign_id=campaign.id,
        active_actor_id=active_actor_id,
        current_area=MapAreaView(
            id=current_area.id,
            name=current_area.name,
        ),
        reachable_areas=reachable_areas,
    )
