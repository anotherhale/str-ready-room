"""In-memory test doubles for the calendar and mailbox ports.

These are *not* mocks of internal collaborators: they are genuine alternate
adapters that satisfy the same ports (a second implementation, exactly as a
Google or JMAP adapter would be).  The application services are exercised
against the real SQLAlchemy persistence adapter and these in-memory providers,
so the tests cover real code paths end to end.
"""
from __future__ import annotations

from datetime import datetime

from app.calendar.domain import CalendarEvent, CalendarInfo
from app.calendar.providers.base import CalendarError, CalendarProvider
from app.mailbox.domain import EmailMessage, EmailSummary
from app.mailbox.providers.base import MailboxError, MailboxProvider


class InMemoryCalendarProvider(CalendarProvider):
    """A calendar provider backed by a dict, with CalDAV-like canonical ids."""

    def __init__(self, calendars: dict[str, str] | None = None, *, reachable: bool = True) -> None:
        self._calendars = calendars or {"detachment": "Detachment"}
        self._events: dict[tuple[str, str], CalendarEvent] = {}
        self._reachable = reachable

    def set_reachable(self, reachable: bool) -> None:
        self._reachable = reachable

    def seed(self, event: CalendarEvent) -> None:
        event.calendar_id = self.resolve_calendar_id(event.calendar_id)
        self._events[(event.calendar_id, event.uid)] = event

    def list_calendars(self) -> list[CalendarInfo]:
        if not self._reachable:
            raise CalendarError("provider offline", status=502)
        return [CalendarInfo(id=self._canonical(key), name=name) for key, name in self._calendars.items()]

    def list_events(self, calendar_id: str) -> list[CalendarEvent]:
        if not self._reachable:
            raise CalendarError("provider offline", status=502)
        canonical = self.resolve_calendar_id(calendar_id)
        # A real provider reports each event under the requested calendar id.
        return [e for (cal, _uid), e in self._events.items() if cal == canonical]

    def create_event(self, event: CalendarEvent) -> CalendarEvent:
        if not self._reachable:
            raise CalendarError("provider offline", status=502)
        canonical = self.resolve_calendar_id(event.calendar_id)
        key = (canonical, event.uid)
        if key in self._events:
            raise CalendarError("already exists", status=409, code="conflict")
        event.calendar_id = canonical
        event.href = f"{canonical}{event.uid}.ics"
        self._events[key] = event
        return event

    def delete_event(self, calendar_id: str, uid: str, href: str | None = None) -> None:
        if not self._reachable:
            raise CalendarError("provider offline", status=502)
        self._events.pop((self.resolve_calendar_id(calendar_id), uid), None)

    def resolve_calendar_id(self, calendar_ref: str) -> str:
        return self._canonical(calendar_ref)

    @staticmethod
    def _canonical(ref: str) -> str:
        # Mirrors the CalDAV adapter's canonical-path shape so a created event
        # caches under the same key list_events returns (DECISIONS D-032).
        return f"/{ref.strip('/')}/"


class InMemoryMailboxProvider(MailboxProvider):
    """A mailbox provider backed by a list, with a switchable reachability."""

    def __init__(self, *, reachable: bool = True) -> None:
        self._messages: list[tuple[str, EmailMessage]] = []
        self._reachable = reachable

    def set_reachable(self, reachable: bool) -> None:
        self._reachable = reachable

    def add(
        self,
        *,
        message_id: str,
        sender: str = "ops@detachment.demo",
        subject: str = "Subject",
        body: str = "Body",
        received_at: datetime | None = None,
    ) -> None:
        self._messages.append(
            (
                message_id,
                EmailMessage(
                    message_id=message_id,
                    sender=sender,
                    subject=subject,
                    received_at=received_at,
                    body=body,
                ),
            )
        )

    def list_messages(self, *, limit: int = 20) -> list[EmailSummary]:
        if not self._reachable:
            raise MailboxError("mailbox offline", status=502)
        recent = list(reversed(self._messages))[:limit]
        return [
            EmailSummary(
                message_id=m.message_id,
                sender=m.sender,
                subject=m.subject,
                received_at=m.received_at,
                snippet=m.body[:120],
            )
            for _key, m in recent
        ]

    def get_message(self, message_id: str) -> EmailMessage:
        if not self._reachable:
            raise MailboxError("mailbox offline", status=502)
        for key, message in self._messages:
            if key == message_id:
                return message
        raise MailboxError(f"Message {message_id!r} not found", status=404, code="not_found")
