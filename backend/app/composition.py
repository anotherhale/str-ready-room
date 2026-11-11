"""Composition root.

The single place that selects concrete adapters from configuration and wires
application services.  Nothing inner knows which adapter is chosen.
"""
from __future__ import annotations

from dataclasses import dataclass

from .adapters.authorization.registry import build_authorizer
from .adapters.identity.registry import build_auth_provider
from .adapters.ids import UuidIdGenerator
from .adapters.persistence.registry import build_database_factory
from .application.ports.clock import Clock, IdGenerator
from .application.ports.identity import AuthorizationPort, AuthProvider
from .application.ports.persistence import DatabaseFactoryPort
from .application.services.briefing_service import BriefingService
from .application.services.category_service import CategoryService
from .application.services.dashboard_service import DashboardService
from .application.services.demo_service import DemoService
from .application.services.recurrence_service import RecurrenceService
from .application.services.settings_service import SettingsService
from .application.services.task_service import TaskService
from .config import Settings
from .domain.shared.clock import FixedClock, SystemClock


@dataclass
class Container:
    """The wired object graph for the application."""

    settings: Settings
    database: DatabaseFactoryPort
    auth_provider: AuthProvider
    authorizer: AuthorizationPort
    clock: Clock
    ids: IdGenerator
    tasks: TaskService
    dashboard: DashboardService
    briefing: BriefingService
    settings_service: SettingsService
    categories: CategoryService
    recurrence: RecurrenceService
    demo: DemoService


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    database = build_database_factory(settings)
    auth_provider = build_auth_provider(settings)
    authorizer = build_authorizer(settings)
    clock = _build_clock(settings)
    ids = UuidIdGenerator()

    return Container(
        settings=settings,
        database=database,
        auth_provider=auth_provider,
        authorizer=authorizer,
        clock=clock,
        ids=ids,
        tasks=TaskService(database, authorizer, clock, ids),
        dashboard=DashboardService(database, authorizer, clock),
        briefing=BriefingService(database, authorizer, clock),
        settings_service=SettingsService(database, authorizer, clock, ids),
        categories=CategoryService(database, authorizer, clock, ids),
        recurrence=RecurrenceService(database, authorizer, clock),
        demo=DemoService(database, authorizer, clock, ids),
    )


def _build_clock(settings: Settings):
    if settings.fixed_now_utc:
        from datetime import datetime

        return FixedClock(datetime.fromisoformat(settings.fixed_now_utc))
    return SystemClock()
