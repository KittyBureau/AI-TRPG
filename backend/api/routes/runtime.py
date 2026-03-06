from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.runtime_status import refresh_runtime_readiness, unlock_runtime_credentials

router = APIRouter(prefix="/runtime", tags=["runtime"])


class RuntimeStatusResponse(BaseModel):
    ready: bool
    reason: str


class RuntimeUnlockRequest(BaseModel):
    passphrase: str


@router.get("/status", response_model=RuntimeStatusResponse)
def runtime_status() -> RuntimeStatusResponse:
    return RuntimeStatusResponse(**refresh_runtime_readiness())


@router.post("/unlock", response_model=RuntimeStatusResponse)
def runtime_unlock(request: RuntimeUnlockRequest) -> RuntimeStatusResponse:
    return RuntimeStatusResponse(**unlock_runtime_credentials(request.passphrase))
