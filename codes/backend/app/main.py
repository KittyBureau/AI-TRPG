from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.services import llm_client
from backend.services import character_service

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
