from getpass import getpass
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.secrets.manager import is_unlocked, SecretsError, unlock
from backend.services import character_service
from backend.services import llm_client
from backend.services import world_movement

app = FastAPI()

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = REPO_ROOT / "frontend" / "public"
INDEX_FILE = FRONTEND_DIR / "index.html"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class TurnRequest(BaseModel):
    player_text: str


class TurnResponse(BaseModel):
    say: str


class CharacterGenerateRequest(BaseModel):
    user_text: str


class CharacterRenameRequest(BaseModel):
    character: dict
    new_name: str
    comment: str | None = None


class MovementPathsRequest(BaseModel):
    entity_id: str
    max_depth: int = 3
    max_paths: int = 20
    risk_ceiling: str = "medium"


class ApplyMoveRequest(BaseModel):
    entity_id: str
    path_id: str


@app.on_event("startup")
async def ensure_secrets_unlocked() -> None:
    if is_unlocked():
        return
    try:
        password = getpass("Secrets password: ")
        unlock(password)
    except SecretsError as exc:
        raise RuntimeError(str(exc)) from exc


@app.get("/", include_in_schema=False)
async def index():
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    return JSONResponse(status_code=404, content={"say": "Frontend not found."})


@app.post("/turn", response_model=TurnResponse)
async def turn(req: TurnRequest):
    try:
        say = await llm_client.generate_say(req.player_text)
        return TurnResponse(say=say)
    except llm_client.LLMError as exc:
        return JSONResponse(status_code=500, content={"say": f"ERROR: {exc}"})


@app.get("/character", include_in_schema=False)
async def character_page():
    page_file = FRONTEND_DIR / "character.html"
    if page_file.exists():
        return FileResponse(page_file)
    return JSONResponse(status_code=404, content={"status": "ERROR", "message": "Character page not found."})


@app.post("/api/characters/generate")
async def generate_character(req: CharacterGenerateRequest):
    try:
        character, comment = await character_service.generate_character(req.user_text)
        saved_path = character_service.save_character(character)
        return {
            "status": "OK",
            "character": character,
            "comment": comment,
            "saved_path": saved_path,
        }
    except character_service.NameConflictError as exc:
        return {
            "status": "NAME_CONFLICT",
            "character": character,
            "conflict_name": exc.name,
            "comment": comment,
            "message": "Character name already exists.",
        }
    except character_service.CharacterError as exc:
        return JSONResponse(status_code=400, content={"status": "ERROR", "message": str(exc)})


@app.post("/api/characters/rename_and_save")
async def rename_and_save(req: CharacterRenameRequest):
    try:
        character = character_service.rename_character(req.character, req.new_name)
        saved_path = character_service.save_character(character)
        payload = {"status": "OK", "character": character, "saved_path": saved_path}
        if req.comment:
            payload["comment"] = req.comment
        return payload
    except character_service.NameConflictError as exc:
        return {
            "status": "NAME_CONFLICT",
            "conflict_name": exc.name,
            "message": "Character name already exists.",
        }
    except character_service.CharacterError as exc:
        return JSONResponse(status_code=400, content={"status": "ERROR", "message": str(exc)})


@app.post("/api/world/get_movement_paths")
async def get_movement_paths(req: MovementPathsRequest):
    try:
        return world_movement.get_movement_paths(
            req.entity_id,
            max_depth=req.max_depth,
            max_paths=req.max_paths,
            risk_ceiling=req.risk_ceiling,
        )
    except world_movement.WorldMovementError as exc:
        return JSONResponse(status_code=400, content={"status": "ERROR", "message": str(exc)})


@app.post("/api/world/apply_move")
async def apply_move(req: ApplyMoveRequest):
    try:
        return world_movement.apply_move(req.entity_id, req.path_id)
    except world_movement.WorldMovementError as exc:
        return JSONResponse(status_code=400, content={"status": "ERROR", "message": str(exc)})
