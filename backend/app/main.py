"""FastAPI application entry point.

Wires the composition root into the ASGI app, registers error handlers, and on
startup initialises the schema and (idempotently) seeds demonstration data.
"""
from __future__ import annotations

import asyncio
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
    principal = container.auth_provider.resolve_current_principal(RequestContext())
    if container.settings.seed_on_startup:
        container.demo.seed_if_needed(principal)

    # Optional integration seeding is best-effort *and* non-blocking: the
    # auxiliary containers may still be booting, so we never delay API readiness
    # waiting on them (see DECISIONS D-028).
    tasks = _integration_seed_tasks(container, principal)
    for coro in tasks:
        asyncio.create_task(coro)

    yield


def _integration_seed_tasks(container, principal):  # noqa: ANN001
    from .calendar.providers.registry import DISABLED as CALENDAR_DISABLED
    from .mailbox.providers.registry import DISABLED as EMAIL_DISABLED

    calendar_on = container.settings.calendar_provider.strip().lower() not in CALENDAR_DISABLED
    email_on = container.settings.email_provider.strip().lower() not in EMAIL_DISABLED

    def seed_calendar() -> None:
        # Seed the provider, then refresh the app cache so the Calendar view is
        # populated on first load instead of requiring a manual Sync.
        container.integration_seed.seed_calendar_if_needed(principal)
        if container.settings.calendar_sync_on_startup:
            container.calendar.sync_quietly(principal)

    coros = []
    if calendar_on:
        coros.append(asyncio.to_thread(seed_calendar))
    if email_on:
        coros.append(asyncio.to_thread(container.integration_seed.seed_mailbox_if_needed, principal))
    return coros


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
