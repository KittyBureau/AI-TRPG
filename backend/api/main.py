from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import campaign, chat, settings


def create_app() -> FastAPI:
    app = FastAPI(title="AI TRPG Backend")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(campaign.router)
    app.include_router(chat.router)
    app.include_router(settings.router)
    return app


app = create_app()
