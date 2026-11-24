"""In-memory test doubles for the calendar and mailbox ports.

These are *not* mocks of internal collaborators: they are genuine alternate
adapters that satisfy the same ports (a second implementation, exactly as a
Google or JMAP adapter would be).  The application services are exercised
against the real SQLAlchemy persistence adapter and these in-memory providers,
so the tests cover real code paths end to end.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.calendar.domain import CalendarEvent, CalendarInfo
from app.calendar.providers.base import CalendarError, CalendarProvider
from app.domain.identity.identity import RequestContext
from app.domain.identity.principal import Principal
from app.domain.shared.errors import AuthenticationError
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

    def purge(self) -> int:
        """Mirror the real adapter: drop every message, report the count removed."""
        if not self._reachable:
            raise MailboxError("mailbox offline", status=502)
        removed = len(self._messages)
        self._messages.clear()
        return removed


# -- multi-principal identity harness (test-only) --------------------------

class MembershipState(StrEnum):
    """Membership lifecycle states a test principal can hold."""

    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"
    REMOVED = "removed"


#: Demo aliases that today's authorizer understands.  Only the two roles with a
#: live demo grant are mapped; the rest resolve as pure ADR-004 roles so a test
#: cannot pass with permissions the role will never hold (DECISIONS C-007).
_DEMO_ALIAS_BY_ROLE = {"squadron_admin": "operator", "read_only": "viewer"}


@dataclass(frozen=True)
class TestMember:
    """A synthetic squadron member: the fixture skeleton for later phases."""

    user_id: str
    display_name: str
    role: str
    timezone: str = "America/Denver"
    squadron_id: str = "squadron-1"
    team_id: str | None = "team-alpha"
    duty_position: str | None = None
    membership_state: MembershipState = MembershipState.ACTIVE

    @property
    def is_active(self) -> bool:
        return self.membership_state is MembershipState.ACTIVE

    def principal(self) -> Principal:
        """Resolve this member to a domain principal, or refuse if not active."""
        if not self.is_active:
            raise AuthenticationError(
                f"{self.user_id} has no usable identity ({self.membership_state.value} membership)"
            )
        roles = {self.role}
        alias = _DEMO_ALIAS_BY_ROLE.get(self.role)
        if alias is not None:
            roles.add(alias)
        return Principal(
            id=self.user_id,
            display_name=self.display_name,
            timezone=self.timezone,
            roles=frozenset(roles),
            attributes=(
                ("squadron_id", self.squadron_id),
                *((("team_id", self.team_id),) if self.team_id else ()),
                *((("duty_position", self.duty_position),) if self.duty_position else ()),
            ),
        )


class TestAuthProvider:
    """A test-only ``AuthProvider`` that resolves whichever principal is selected.

    Selection is explicit: ``select()`` for a whole test, or an
    ``X-Test-Principal`` header for a single request.  With nothing selected it
    raises ``AuthenticationError``, so "no identity" is a real code path.
    """

    scheme = "test"

    #: Header a test may send to act as a specific roster member.
    HEADER = "X-Test-Principal"

    def __init__(self, roster: dict[str, TestMember]) -> None:
        self._roster = roster
        self._selected: str | None = None

    def select(self, user_id: str) -> Principal:
        """Act as ``user_id`` for the rest of the test."""
        member = self._member(user_id)
        self._selected = user_id
        return member.principal()

    def clear(self) -> None:
        self._selected = None

    def _member(self, user_id: str) -> TestMember:
        try:
            return self._roster[user_id]
        except KeyError:
            raise AuthenticationError(f"Unknown test principal {user_id!r}") from None

    def resolve_current_principal(self, context: RequestContext) -> Principal:
        for name, value in context.headers:
            if name.lower() == self.HEADER.lower():
                return self._member(value).principal()
        if self._selected is None:
            raise AuthenticationError("No principal selected for this test request")
        return self._member(self._selected).principal()
