from __future__ import annotations

from json import JSONDecodeError
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from backend.app.debug_resources import build_template_usage_debug
from backend.app.turn_service import TurnService
from backend.domain.models import Campaign
from backend.infra.file_repo import FileRepo

router = APIRouter(prefix="/campaign", tags=["campaign"])


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
    debug: Optional[dict] = None


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


class CampaignStatusMilestoneResponse(BaseModel):
    current: str
    last_advanced_turn: int
    turn_trigger_interval: int
    pressure: int
    pressure_threshold: int
    summary: str


class CampaignStatusSnapshotResponse(BaseModel):
    ended: bool
    reason: Optional[str] = None
    ended_at: Optional[str] = None
    milestone: CampaignStatusMilestoneResponse


class CampaignStatusResponse(CampaignStatusSnapshotResponse):
    campaign_id: str


class AdvanceMilestoneRequest(BaseModel):
    campaign_id: str
    summary: str = ""


class AdvanceMilestoneResponse(BaseModel):
    campaign_id: str
    milestone: CampaignStatusMilestoneResponse


class CampaignSelectedResponse(BaseModel):
    party_character_ids: List[str] = Field(default_factory=list)
    active_actor_id: str


class CampaignGetResponse(BaseModel):
    campaign_id: str
    selected: CampaignSelectedResponse
    actors: List[str] = Field(default_factory=list)
    status: CampaignStatusSnapshotResponse


def _load_campaign_for_get(repo: FileRepo, campaign_id: str) -> Campaign:
    try:
        return repo.get_campaign(campaign_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Campaign invalid: {campaign_id}",
        ) from exc


def _build_campaign_status_snapshot(campaign: Campaign) -> CampaignStatusSnapshotResponse:
    return CampaignStatusSnapshotResponse(
        ended=campaign.lifecycle.ended,
        reason=campaign.lifecycle.reason,
        ended_at=campaign.lifecycle.ended_at,
        milestone=CampaignStatusMilestoneResponse(
            current=campaign.milestone.current,
            last_advanced_turn=campaign.milestone.last_advanced_turn,
            turn_trigger_interval=campaign.milestone.turn_trigger_interval,
            pressure=campaign.milestone.pressure,
            pressure_threshold=campaign.milestone.pressure_threshold,
            summary=campaign.milestone.summary,
        ),
    )


@router.post("/create", response_model=CreateCampaignResponse)
def create_campaign(request: CreateCampaignRequest) -> CreateCampaignResponse:
    world_id = request.world_id or "world_001"
    map_id = request.map_id or "map_001"

    service = _service()
    campaign_id, template_usage, trace_enabled = service.create_campaign_with_template_usage(
        world_id=world_id,
        map_id=map_id,
        party_character_ids=request.party_character_ids,
        active_actor_id=request.active_actor_id,
    )
    debug_payload = build_template_usage_debug(template_usage) if trace_enabled else None
    return CreateCampaignResponse(campaign_id=campaign_id, debug=debug_payload)


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


@router.get("/get", response_model=CampaignGetResponse)
def get_campaign(campaign_id: str) -> CampaignGetResponse:
    repo = FileRepo(Path.cwd() / "storage")
    campaign = _load_campaign_for_get(repo, campaign_id)
    return CampaignGetResponse(
        campaign_id=campaign.id,
        selected=CampaignSelectedResponse(
            party_character_ids=list(campaign.selected.party_character_ids),
            active_actor_id=campaign.selected.active_actor_id,
        ),
        actors=sorted(campaign.actors.keys()),
        status=_build_campaign_status_snapshot(campaign),
    )


@router.get("/status", response_model=CampaignStatusResponse)
def campaign_status(campaign_id: str) -> CampaignStatusResponse:
    repo = FileRepo(Path.cwd() / "storage")
    campaign = _load_campaign_for_get(repo, campaign_id)
    return CampaignStatusResponse(
        campaign_id=campaign.id,
        **_build_campaign_status_snapshot(campaign).model_dump(),
    )


@router.post("/milestone/advance", response_model=AdvanceMilestoneResponse)
def advance_milestone(request: AdvanceMilestoneRequest) -> AdvanceMilestoneResponse:
    repo = FileRepo(Path.cwd() / "storage")
    try:
        campaign = repo.get_campaign(request.campaign_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    current = campaign.milestone.current
    if current == "intro":
        next_current = "milestone_1"
    elif current.startswith("milestone_") and current.replace("milestone_", "", 1).isdigit():
        next_current = f"milestone_{int(current.replace('milestone_', '', 1)) + 1}"
    else:
        next_current = "milestone_1"
    campaign.milestone.current = next_current
    campaign.milestone.last_advanced_turn += 1
    campaign.milestone.pressure = 0
    campaign.milestone.summary = request.summary
    repo.save_campaign(campaign)
    return AdvanceMilestoneResponse(
        campaign_id=campaign.id,
        milestone=CampaignStatusMilestoneResponse(
            current=campaign.milestone.current,
            last_advanced_turn=campaign.milestone.last_advanced_turn,
            turn_trigger_interval=campaign.milestone.turn_trigger_interval,
            pressure=campaign.milestone.pressure,
            pressure_threshold=campaign.milestone.pressure_threshold,
            summary=campaign.milestone.summary,
        ),
    )
