from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.app.character_library_service import (
    CharacterLibraryNotFoundError,
    CharacterLibraryService,
    CharacterLibraryValidationError,
)
from backend.app.party_load_service import PartyLoadService
from backend.infra.file_repo import FileRepo

router = APIRouter(tags=["character-library"])


def _repo() -> FileRepo:
    return FileRepo(Path.cwd() / "storage")


def _character_library_service() -> CharacterLibraryService:
    return CharacterLibraryService(_repo())


def _party_load_service() -> PartyLoadService:
    repo = _repo()
    return PartyLoadService(repo, character_library_service=CharacterLibraryService(repo))


class CharacterLibrarySummary(BaseModel):
    id: str
    name: str
    summary: str = ""
    tags: List[str] = Field(default_factory=list)


class CharacterLibraryUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str
    summary: str | None = None
    tags: List[str] | None = None
    meta: Dict[str, Any] | None = None

    def to_payload(self) -> Dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump()
        return self.dict()


class CharacterLibraryUpsertResponse(BaseModel):
    ok: bool
    character_id: str
    fact: Dict[str, Any]


class PartyLoadRequest(BaseModel):
    character_id: str
    set_active_if_empty: bool = True


class PartyLoadResponse(BaseModel):
    ok: bool
    campaign_id: str
    character_id: str
    party_character_ids: List[str] = Field(default_factory=list)
    active_actor_id: str


@router.get(
    "/characters/library",
    response_model=List[CharacterLibrarySummary],
)
def list_characters_library() -> List[CharacterLibrarySummary]:
    service = _character_library_service()
    return [CharacterLibrarySummary(**item) for item in service.list_facts()]


@router.get("/characters/library/{character_id}")
def get_character_library_fact(character_id: str) -> Dict[str, Any]:
    service = _character_library_service()
    try:
        return service.get_fact(character_id)
    except CharacterLibraryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CharacterLibraryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/characters/library",
    response_model=CharacterLibraryUpsertResponse,
)
def upsert_character_library_fact(
    request: CharacterLibraryUpsertRequest,
) -> CharacterLibraryUpsertResponse:
    service = _character_library_service()
    try:
        fact = service.upsert_fact(request.to_payload())
    except CharacterLibraryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CharacterLibraryUpsertResponse(ok=True, character_id=fact["id"], fact=fact)


@router.post(
    "/campaigns/{campaign_id}/party/load",
    response_model=PartyLoadResponse,
)
def load_character_to_party(
    campaign_id: str,
    request: PartyLoadRequest,
) -> PartyLoadResponse:
    service = _party_load_service()
    try:
        result = service.load_character_to_campaign(
            campaign_id,
            request.character_id,
            set_active_if_empty=request.set_active_if_empty,
        )
    except CharacterLibraryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CharacterLibraryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PartyLoadResponse(**result)
