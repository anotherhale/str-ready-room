"""Shared pytest fixtures.

Integration tests run against a real temporary SQLite database (file-based so
behaviour matches production).  ``READY_ROOM_TEST_DATABASE_URL`` can point the
same suite at PostgreSQL (see M8).
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime

import pytest

from app.adapters.authorization.registry import build_authorizer
from app.adapters.ids import SequentialIdGenerator
from app.adapters.persistence.sqlalchemy.database import SqlAlchemyDatabaseFactory
from app.application.services.briefing_service import BriefingService
from app.application.services.category_service import CategoryService
from app.application.services.dashboard_service import DashboardService
from app.application.services.demo_service import DemoService
from app.application.services.recurrence_service import RecurrenceService
from app.application.services.settings_service import SettingsService
from app.application.services.task_service import TaskService
from app.domain.identity.principal import Principal
from app.domain.shared.clock import FixedClock

#: A fixed "now" so tests are deterministic.  Chosen mid-morning UTC so the
#: operator's New York local date is unambiguous.
FIXED_NOW = datetime(2026, 3, 10, 13, 0, 0)  # 09:00 America/New_York
FIXED_TODAY = date(2026, 3, 10)


@pytest.fixture
def database_url(tmp_path):
    """Yield a database URL.

    Default: a fresh temporary SQLite file per test.  When
    ``READY_ROOM_TEST_DATABASE_URL`` points at PostgreSQL, each test gets its own
    schema so the identical suite runs against PostgreSQL with isolation.
    """
    override = os.environ.get("READY_ROOM_TEST_DATABASE_URL")
    if not override:
        yield f"sqlite:///{tmp_path}/ready_room_test.db"
        return

    schema = f"test_{uuid.uuid4().hex[:12]}"
    separator = "&" if "?" in override else "?"
    # psycopg accepts a libpq `options` parameter; set search_path to the schema.
    url = f"{override}{separator}options=-csearch_path%3D{schema}"
    _create_schema(override, schema)
    try:
        yield url
    finally:
        _drop_schema(override, schema)


def _create_schema(base_url: str, schema: str) -> None:
    import psycopg

    with psycopg.connect(_libpq_dsn(base_url)) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
        conn.commit()


def _drop_schema(base_url: str, schema: str) -> None:
    import psycopg

    with psycopg.connect(_libpq_dsn(base_url)) as conn:
        conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        conn.commit()


def _libpq_dsn(sqlalchemy_url: str) -> str:
    """Convert a SQLAlchemy postgres URL to a libpq DSN for psycopg.connect."""
    url = sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://")
    return url


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(FIXED_NOW)


@pytest.fixture
def principal() -> Principal:
    return Principal(
        id="maverick",
        display_name="Maverick",
        timezone="America/New_York",
        roles=frozenset({"operator"}),
    )


@pytest.fixture
def database(database_url) -> SqlAlchemyDatabaseFactory:
    factory = SqlAlchemyDatabaseFactory(database_url)
    factory.init_schema()
    return factory


@pytest.fixture
def services(database, clock, principal):
    """A wired set of application services against the real adapter."""
    authorizer = build_authorizer(type("S", (), {"authorization_engine": "policy"})())
    ids = SequentialIdGenerator()

    task_service = TaskService(database, authorizer, clock, ids)
    settings_service = SettingsService(database, authorizer, clock, ids)
    demo_service = DemoService(database, authorizer, clock, ids)

    # Initialise settings + default categories for the operator.
    settings_service.get_settings(principal)

    return {
        "tasks": task_service,
        "settings": settings_service,
        "categories": CategoryService(database, authorizer, clock, ids),
        "dashboard": DashboardService(database, authorizer, clock),
        "briefing": BriefingService(database, authorizer, clock),
        "recurrence": RecurrenceService(database, authorizer, clock),
        "demo": demo_service,
        "database": database,
        "authorizer": authorizer,
        "ids": ids,
        "clock": clock,
        "principal": principal,
    }


@pytest.fixture
def viewer() -> Principal:
    """A principal with read-only permissions, for authorization tests."""
    return Principal(
        id="observer",
        display_name="Observer",
        timezone="America/New_York",
        roles=frozenset({"viewer"}),
    )
