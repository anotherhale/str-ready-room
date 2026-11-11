"""FastAPI application entry point.

Wires the composition root into the ASGI app, registers error handlers, and on
startup initialises the schema and (idempotently) seeds demonstration data.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.error_handlers import register_error_handlers
from .api.routers import api_router
from .composition import build_container
from .config import get_settings
from .domain.identity.identity import RequestContext


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = build_container(get_settings())
    app.state.container = container

    # Initialise schema and seed idempotently.
    container.database.init_schema()
    if container.settings.seed_on_startup:
        principal = container.auth_provider.resolve_current_principal(RequestContext())
        container.demo.seed_if_needed(principal)

    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="READY ROOM",
        version="0.1.0",
        description="Operational awareness for a single detachment officer.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
