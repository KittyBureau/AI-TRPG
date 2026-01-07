from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import llm_client

app = FastAPI()

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class TurnRequest(BaseModel):
    player_text: str


class TurnResponse(BaseModel):
    say: str


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
