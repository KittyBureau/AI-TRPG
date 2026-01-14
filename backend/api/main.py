from __future__ import annotations

from fastapi import FastAPI

from backend.api.routes import campaign, chat, settings


def create_app() -> FastAPI:
    app = FastAPI(title="AI TRPG Backend")
    app.include_router(campaign.router)
    app.include_router(chat.router)
    app.include_router(settings.router)
    return app


app = create_app()
