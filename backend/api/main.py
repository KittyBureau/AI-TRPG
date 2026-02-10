from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import campaign, characters, chat, map, settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI TRPG Backend",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(campaign.router, prefix="/api/v1")
    app.include_router(characters.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(map.router, prefix="/api/v1")
    app.include_router(settings.router, prefix="/api/v1")
    return app


app = create_app()
