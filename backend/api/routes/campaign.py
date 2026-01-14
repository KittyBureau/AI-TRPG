from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.turn_service import TurnService
from backend.infra.file_repo import FileRepo

router = APIRouter(prefix="/api/campaign", tags=["campaign"])


def _service() -> TurnService:
    storage_root = Path.cwd() / "storage"
    repo = FileRepo(storage_root)
    return TurnService(repo)


class CreateCampaignRequest(BaseModel):
    world_id: Optional[str] = None
    map_id: Optional[str] = None
    party_character_ids: Optional[List[str]] = None
    active_actor_id: Optional[str] = None


class CreateCampaignResponse(BaseModel):
    campaign_id: str


class CampaignSummaryResponse(BaseModel):
    id: str
    world_id: str
    active_actor_id: str


class CampaignListResponse(BaseModel):
    campaigns: List[CampaignSummaryResponse] = Field(default_factory=list)


class SelectActorRequest(BaseModel):
    campaign_id: str
    active_actor_id: str


class SelectActorResponse(BaseModel):
    campaign_id: str
    active_actor_id: str


@router.post("/create", response_model=CreateCampaignResponse)
def create_campaign(request: CreateCampaignRequest) -> CreateCampaignResponse:
    world_id = request.world_id or "world_001"
    map_id = request.map_id or "map_001"
    party_character_ids = request.party_character_ids or ["pc_001"]
    active_actor_id = request.active_actor_id or party_character_ids[0]
    if active_actor_id not in party_character_ids:
        party_character_ids = [active_actor_id] + party_character_ids

    service = _service()
    campaign_id = service.create_campaign(
        world_id=world_id,
        map_id=map_id,
        party_character_ids=party_character_ids,
        active_actor_id=active_actor_id,
    )
    return CreateCampaignResponse(campaign_id=campaign_id)


@router.get("/list", response_model=CampaignListResponse)
def list_campaigns() -> CampaignListResponse:
    service = _service()
    campaigns = service.list_campaigns()
    return CampaignListResponse(
        campaigns=[
            CampaignSummaryResponse(
                id=campaign.id,
                world_id=campaign.world_id,
                active_actor_id=campaign.active_actor_id,
            )
            for campaign in campaigns
        ]
    )


@router.post("/select_actor", response_model=SelectActorResponse)
def select_actor(request: SelectActorRequest) -> SelectActorResponse:
    service = _service()
    try:
        campaign = service.select_actor(request.campaign_id, request.active_actor_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SelectActorResponse(
        campaign_id=campaign.id,
        active_actor_id=campaign.selected.active_actor_id,
    )
