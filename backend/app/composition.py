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
from .application.ports.mail import MailSender
from .application.ports.persistence import DatabaseFactoryPort
from .application.services.briefing_service import BriefingService
from .application.services.calendar_service import CalendarService
from .application.services.category_service import CategoryService
from .application.services.dashboard_service import DashboardService
from .application.services.demo_service import DemoService
from .application.services.email_service import EmailService
from .application.services.integration_seed_service import IntegrationSeedService
from .application.services.recurrence_service import RecurrenceService
from .application.services.settings_service import SettingsService
from .application.services.task_service import TaskService
from .calendar.providers.base import CalendarProvider
from .calendar.providers.registry import build_calendar_provider
from .config import Settings
from .domain.shared.clock import FixedClock, SystemClock
from .mailbox.providers.base import MailboxProvider
from .mailbox.providers.registry import build_mailbox_provider


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
    calendar: CalendarService
    email: EmailService
    integration_seed: IntegrationSeedService
    #: Optional integrations; ``None`` when disabled in configuration.
    calendar_provider: CalendarProvider | None = None
    mailbox_provider: MailboxProvider | None = None


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    database = build_database_factory(settings)
    auth_provider = build_auth_provider(settings)
    authorizer = build_authorizer(settings)
    clock = _build_clock(settings)
    ids = UuidIdGenerator()

    calendar_provider = build_calendar_provider(settings)
    mailbox_provider = build_mailbox_provider(settings)
    mail_sender = _build_mail_sender(settings) if mailbox_provider is not None else None

    calendar_service = CalendarService(
        database, authorizer, clock, ids,
        provider=calendar_provider,
        default_calendar=settings.caldav_calendar,
    )
    email_service = EmailService(
        database, authorizer, clock, ids,
        provider=mailbox_provider,
        mailbox_name=settings.imap_mailbox,
    )
    integration_seed = IntegrationSeedService(
        database, clock,
        calendar_provider=calendar_provider,
        default_calendar=settings.caldav_calendar,
        mail_sender=mail_sender,
        mailbox_provider=mailbox_provider,
    )

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
        demo=DemoService(
            database, authorizer, clock, ids,
            integration_seed=integration_seed,
            calendar=calendar_service,
            mail_sender=mail_sender,
            default_calendar=settings.caldav_calendar,
        ),
        calendar=calendar_service,
        email=email_service,
        integration_seed=integration_seed,
        calendar_provider=calendar_provider,
        mailbox_provider=mailbox_provider,
    )


def _build_mail_sender(settings: Settings) -> MailSender:
    from .application.ports.mail import SmtpMailSender

    return SmtpMailSender(host=settings.smtp_host, port=settings.smtp_port)


def _build_clock(settings: Settings):
    if settings.fixed_now_utc:
        from datetime import datetime

        return FixedClock(datetime.fromisoformat(settings.fixed_now_utc))
    return SystemClock()
