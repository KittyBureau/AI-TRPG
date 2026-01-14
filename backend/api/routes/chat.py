from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.turn_service import TurnService
from backend.infra.file_repo import FileRepo

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _service() -> TurnService:
    storage_root = Path.cwd() / "storage"
    repo = FileRepo(storage_root)
    return TurnService(repo)


class TurnRequest(BaseModel):
    campaign_id: str
    user_input: str
    actor_id: Optional[str] = None


class TurnResponse(BaseModel):
    narrative_text: str
    dialog_type: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    applied_actions: List[Dict[str, Any]] = Field(default_factory=list)
    tool_feedback: Optional[Dict[str, Any]] = None
    conflict_report: Optional[Dict[str, Any]] = None
    state_summary: Dict[str, Any]


@router.post("/turn", response_model=TurnResponse)
def submit_turn(request: TurnRequest) -> TurnResponse:
    service = _service()
    try:
        response = service.submit_turn(
            request.campaign_id, request.user_input, actor_id=request.actor_id
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TurnResponse(**response)
