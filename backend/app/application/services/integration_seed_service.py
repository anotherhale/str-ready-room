"""Integration seeding: demo calendar events and demo mailbox messages.

Kept separate from the core task seed (``DemoService``) and from application
startup (see DECISIONS D-028).  The auxiliary containers may still be booting
when the API is ready, so both seeders are **best-effort**, retry a few times,
and log rather than raise.  Each has its own marker row so it runs at most once
and never duplicates data across restarts.

The calendar events are built with **timezone-aware** local datetimes (see
DECISIONS D-029): a naive datetime is treated as UTC by the provider, which
would shift "flight quarters at 07:30" to 00:30 local.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from ...calendar.domain import CalendarEvent
from ...calendar.providers.base import CalendarError, CalendarProvider
from ...domain.settings.entities import CURRENT_CALENDAR_SEED_VERSION, CURRENT_EMAIL_SEED_VERSION
from ...domain.shared.clock import Clock
from ...mailbox.providers.base import MailboxError, MailboxProvider
from ..ports.mail import MailSender, MailSenderError
from ..ports.persistence import DatabaseFactoryPort

logger = logging.getLogger("ready_room.seed")

DEMO_SENDER = "ops@detachment.demo"
DEMO_RECIPIENT = "maverick@detachment.demo"


class IntegrationSeedService:
    """Seeds the optional calendar and mailbox integrations."""

    def __init__(
        self,
        database: DatabaseFactoryPort,
        clock: Clock,
        *,
        calendar_provider: CalendarProvider | None = None,
        default_calendar: str = "detachment",
        mail_sender: MailSender | None = None,
        mailbox_provider: MailboxProvider | None = None,
    ) -> None:
        self._database = database
        self._clock = clock
        self._calendar = calendar_provider
        self._default_calendar = default_calendar
        self._mail = mail_sender
        self._mailbox = mailbox_provider

    # -- markers -------------------------------------------------------
    def _marker(self, principal, field: str) -> int:  # noqa: ANN001
        with self._database.create() as uow:
            settings = uow.settings.get(principal.id)
            return getattr(settings, field, 0) if settings is not None else 0

    def _set_marker(self, principal, field: str, value: int) -> None:  # noqa: ANN001
        from ...domain.settings.entities import OperatorSettings

        with self._database.create() as uow:
            settings = uow.settings.get(principal.id) or OperatorSettings(
                owner_id=principal.id, timezone=principal.timezone
            )
            setattr(settings, field, value)
            settings.updated_at = self._clock.now_utc()
            uow.settings.save(settings)
            uow.commit()

    # -- calendar ------------------------------------------------------
    def seed_calendar_if_needed(self, principal, *, attempts: int = 3) -> bool:  # noqa: ANN001
        if self._calendar is None:
            return False
        if self._marker(principal, "calendar_seed_version") >= CURRENT_CALENDAR_SEED_VERSION:
            return False

        events = self._demo_calendar_events(principal.timezone)
        for attempt in range(1, attempts + 1):
            try:
                calendar_id = self._calendar.resolve_calendar_id(self._default_calendar)
                # Reconcile against what the provider already holds: a restart
                # (or a reset) with a fresh application DB but a persistent
                # provider must not re-create the demo events and then mistake
                # the resulting conflict for "provider unavailable".
                existing_uids = {e.uid for e in self._calendar.list_events(calendar_id)}
                for event in events:
                    if event.uid in existing_uids:
                        continue
                    event.calendar_id = calendar_id
                    try:
                        self._calendar.create_event(event)
                    except CalendarError as exc:
                        # A racing create, or an event already present under a
                        # uid we did not list, is not a seeding failure.
                        if exc.code != "conflict":
                            raise
            except CalendarError as exc:
                logger.warning(
                    "calendar seed attempt %s/%s failed: %s", attempt, attempts, exc.message
                )
                continue
            self._set_marker(principal, "calendar_seed_version", CURRENT_CALENDAR_SEED_VERSION)
            logger.info("seeded demo calendar events (provider now holds %s)", len(existing_uids) or len(events))
            return True
        logger.warning("calendar seeding skipped; provider unavailable")
        return False

    def _demo_calendar_events(self, timezone_name: str) -> list[CalendarEvent]:
        """Build the demo events anchored to the operator's local zone."""
        zone = ZoneInfo(timezone_name)
        today = self._clock.today(timezone_name)
        now = self._clock.now_utc()

        def at(day_offset: int, hour: int, minute: int = 0) -> datetime:
            return datetime.combine(today + timedelta(days=day_offset), time(hour, minute), tzinfo=zone)

        return [
            CalendarEvent(
                uid="demo-flight-quarters",
                calendar_id=self._default_calendar,
                summary="Detachment flight quarters",
                start=at(0, 7, 30),
                end=at(0, 8, 15),
                location="Ready room",
                description="Morning brief: flying schedule, maintenance status, admin items.",
                updated_at=now,
            ),
            CalendarEvent(
                uid="demo-tow-bar-inspection",
                calendar_id=self._default_calendar,
                summary="Tow bar inspection window",
                start=at(2, 13, 0),
                end=at(2, 14, 0),
                location="Hangar 2",
                description="Machine shop inspection slot for the tow bar.",
                updated_at=now,
            ),
            CalendarEvent(
                uid="demo-range-slot",
                calendar_id=self._default_calendar,
                summary="Range slot — qualification flights",
                start=at(3, 9, 0),
                end=at(3, 12, 0),
                location="North range",
                description="Personnel qualification sorties.",
                updated_at=now,
            ),
            CalendarEvent(
                uid="demo-admin-board",
                calendar_id=self._default_calendar,
                summary="Administrative review board",
                start=at(10, 15, 0),
                end=at(10, 16, 0),
                description="Next week's administrative requirements.",
                updated_at=now,
            ),
        ]

    # -- mailbox -------------------------------------------------------
    def seed_mailbox_if_needed(self, principal, *, attempts: int = 3) -> bool:  # noqa: ANN001
        if self._mail is None:
            return False

        # Idempotency is keyed on the demo messages' own Message-IDs, not only on
        # the marker.  A demo mail server (GreenMail) keeps messages in memory, so
        # the marker can say "seeded" while the mailbox is empty (after the mail
        # container restarts) -- or the marker can be cleared (after a demo reset)
        # while the mailbox still holds the messages.  Reconcile against the
        # mailbox so the demo state is always restored and never duplicated.
        marker_ok = self._marker(principal, "email_seed_version") >= CURRENT_EMAIL_SEED_VERSION
        existing = self._existing_message_ids()
        if marker_ok and (existing is None or existing):
            return False

        messages = self._demo_messages()
        pending = messages if not existing else [m for m in messages if m["message_id"] not in existing]
        if not pending:
            self._set_marker(principal, "email_seed_version", CURRENT_EMAIL_SEED_VERSION)
            return False

        for attempt in range(1, attempts + 1):
            try:
                for message in pending:
                    self._mail.send(
                        sender=DEMO_SENDER,
                        recipient=DEMO_RECIPIENT,
                        subject=message["subject"],
                        body=message["body"],
                        message_id=message["message_id"],
                    )
            except MailSenderError as exc:
                logger.warning("mailbox seed attempt %s/%s failed: %s", attempt, attempts, exc)
                continue
            self._set_marker(principal, "email_seed_version", CURRENT_EMAIL_SEED_VERSION)
            logger.info("seeded %s demo mailbox messages", len(pending))
            return True
        logger.warning("mailbox seeding skipped; mail server unavailable")
        return False

    def _existing_message_ids(self) -> set[str] | None:
        """Best-effort set of Message-IDs already present in the mailbox.

        Returns ``None`` when there is no mailbox provider to inspect (or it is
        unreachable), meaning "cannot tell" -- the caller then falls back to the
        marker.  A reachable but empty mailbox returns an empty set, so the demo
        messages are (re)seeded.
        """
        if self._mailbox is None:
            return None
        try:
            return {m.message_id for m in self._mailbox.list_messages(limit=100)}
        except MailboxError:
            return None

    @staticmethod
    def _demo_messages() -> list[dict[str, str]]:
        return [
            {
                "message_id": "<demo-1@detachment.demo>",
                "subject": "Tow bar inspection — need a signature",
                "body": (
                    "Maverick,\n\nThe machine shop flagged the tow bar for inspection before "
                    "the next evolution. Please confirm the window and sign the work order.\n\n"
                    "- Maintenance"
                ),
            },
            {
                "message_id": "<demo-2@detachment.demo>",
                "subject": "Training records overdue",
                "body": (
                    "Sir,\n\nTwo training jacket updates are still outstanding to the squadron "
                    "admin office. Can you route them this week?\n\n- Admin"
                ),
            },
            {
                "message_id": "<demo-3@detachment.demo>",
                "subject": "Logistics consumables inventory",
                "body": (
                    "Detachment,\n\nWe should count consumables soon and flag anything below the "
                    "reorder threshold before the next supply run.\n\n- Logistics"
                ),
            },
        ]
