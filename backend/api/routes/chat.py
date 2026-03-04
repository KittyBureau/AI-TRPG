from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.turn_service import CampaignBusyError, SemanticGuardError, TurnService
from backend.infra.file_repo import FileRepo

router = APIRouter(prefix="/chat", tags=["chat"])


def _service() -> TurnService:
    storage_root = Path.cwd() / "storage"
    repo = FileRepo(storage_root)
    return TurnService(repo)


class TurnRequest(BaseModel):
    campaign_id: str
    user_input: str
    actor_id: Optional[str] = None
    execution: Optional[Dict[str, Any]] = None


class TurnResponse(BaseModel):
    effective_actor_id: str
    narrative_text: str
    dialog_type: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    applied_actions: List[Dict[str, Any]] = Field(default_factory=list)
    tool_feedback: Optional[Dict[str, Any]] = None
    conflict_report: Optional[Dict[str, Any]] = None
    state_summary: Dict[str, Any]
    debug: Optional[Dict[str, Any]] = None


@router.post("/turn", response_model=TurnResponse)
def submit_turn(request: TurnRequest) -> TurnResponse:
    service = _service()
    execution_actor_id: Optional[str] = None
    if isinstance(request.execution, dict):
        candidate = request.execution.get("actor_id")
        if isinstance(candidate, str) and candidate.strip():
            execution_actor_id = candidate.strip()
    effective_actor_id = execution_actor_id or request.actor_id
    try:
        response = service.submit_turn(
            request.campaign_id, request.user_input, actor_id=effective_actor_id
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SemanticGuardError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CampaignBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TurnResponse(**response)
