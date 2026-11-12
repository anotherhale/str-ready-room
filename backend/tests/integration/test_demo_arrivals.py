"""Tests for the live demo arrival injection (D-039).

``POST /api/demo/arrivals`` (``DemoService.inject_arrivals``) delivers one new
incoming email and one new calendar event on demand.  The provider/mailer are
genuine alternate adapters and persistence is the real adapter, so the whole
use case is exercised without mocks.  The behaviour under test:

* a new message lands in the mailbox and a new event on the calendar;
* successive calls rotate content and never collide on identifiers;
* a disabled or unreachable integration is reported, not raised;
* the action is authorized (``demo:simulate``).
"""
from __future__ import annotations

import pytest

from app.application.ports.mail import MailSender, MailSenderError
from app.application.services.calendar_service import CalendarService
from app.application.services.demo_service import DemoService
from app.domain.authorization.permissions import Permission
from app.domain.shared.errors import AuthorizationError
from tests.doubles import InMemoryCalendarProvider, InMemoryMailboxProvider


class RecordingMailSender(MailSender):
    """A genuine ``MailSender`` adapter that appends to a mailbox (as SMTP→IMAP does)."""

    def __init__(self, *, mailbox=None, fail: bool = False) -> None:  # noqa: ANN001
        self.sent: list[dict[str, str]] = []
        self._mailbox = mailbox
        self._fail = fail

    def send(self, *, sender: str, recipient: str, subject: str, body: str, message_id: str) -> None:
        if self._fail:
            raise MailSenderError("smtp down")
        self.sent.append({"sender": sender, "recipient": recipient, "subject": subject, "message_id": message_id})
        if self._mailbox is not None:
            self._mailbox.add(message_id=message_id, sender=sender, subject=subject, body=body)


def _demo(services, *, mailbox=None, mailer=None, calendar_provider=None):  # noqa: ANN001
    calendar = None
    if calendar_provider is not None:
        calendar = CalendarService(
            services["database"], services["authorizer"], services["clock"], services["ids"],
            provider=calendar_provider, default_calendar="detachment",
        )
    return DemoService(
        services["database"],
        services["authorizer"],
        services["clock"],
        services["ids"],
        calendar=calendar,
        mail_sender=mailer,
        default_calendar="detachment",
    )


def test_inject_arrivals_delivers_email_and_event(services):
    mailbox = InMemoryMailboxProvider()
    mailer = RecordingMailSender(mailbox=mailbox)
    calendar_provider = InMemoryCalendarProvider()
    demo = _demo(services, mailer=mailer, calendar_provider=calendar_provider)

    result = demo.inject_arrivals(services["principal"])

    assert result.email_delivered is True
    assert result.calendar_delivered is True
    assert len(mailer.sent) == 1
    assert len(mailbox.list_messages()) == 1
    assert len(calendar_provider.list_events("detachment")) == 1


def test_inject_arrivals_is_repeatable_and_rotates(services):
    """Each call is a *new* arrival: content rotates and identifiers are unique."""
    mailbox = InMemoryMailboxProvider()
    mailer = RecordingMailSender(mailbox=mailbox)
    calendar_provider = InMemoryCalendarProvider()
    demo = _demo(services, mailer=mailer, calendar_provider=calendar_provider)
    principal = services["principal"]

    subjects = []
    for _ in range(3):
        result = demo.inject_arrivals(principal)
        assert result.email_delivered and result.calendar_delivered
        subjects.append(result.email_detail)

    # Three distinct messages, three distinct events — no collisions.
    assert len(mailbox.list_messages()) == 3
    assert len(calendar_provider.list_events("detachment")) == 3
    ids = [m["message_id"] for m in mailer.sent]
    assert len(set(ids)) == 3
    # Content rotates (three catalog entries), so not every subject repeats.
    assert len(set(subjects)) == 3


def test_inject_arrivals_reports_unreachable_calendar_without_raising(services):
    mailer = RecordingMailSender(mailbox=InMemoryMailboxProvider())
    calendar_provider = InMemoryCalendarProvider(reachable=False)
    demo = _demo(services, mailer=mailer, calendar_provider=calendar_provider)

    result = demo.inject_arrivals(services["principal"])

    assert result.email_delivered is True
    assert result.calendar_delivered is False
    assert "unavailable" in result.calendar_detail.lower()


def test_inject_arrivals_reports_missing_integrations_without_raising(services):
    """The base stack (no providers) must not error when the demo action is used."""
    demo = _demo(services)  # no mailer, no calendar
    result = demo.inject_arrivals(services["principal"])

    assert result.email_delivered is False
    assert result.calendar_delivered is False
    assert "not configured" in result.email_detail.lower()
    assert "not configured" in result.calendar_detail.lower()


def test_inject_arrivals_reports_mail_failure_without_raising(services):
    mailer = RecordingMailSender(fail=True)
    demo = _demo(services, mailer=mailer)
    result = demo.inject_arrivals(services["principal"])
    assert result.email_delivered is False
    assert "unavailable" in result.email_detail.lower()


def test_inject_arrivals_is_authorized(services, viewer):
    """A principal without ``demo:simulate`` is denied (the same policy path)."""
    from app.domain.authorization.permissions import VIEWER_PERMISSIONS

    assert Permission.DEMO_SIMULATE not in VIEWER_PERMISSIONS

    mailbox = InMemoryMailboxProvider()
    demo = _demo(services, mailer=RecordingMailSender(mailbox=mailbox))

    with pytest.raises(AuthorizationError):
        demo.inject_arrivals(viewer)
    # Nothing was delivered on a denied call.
    assert mailbox.list_messages() == []


def test_inject_arrivals_counter_survives_reset(services):
    """Reset clears the counter, and the next arrival still gets a unique id."""
    mailbox = InMemoryMailboxProvider()
    mailer = RecordingMailSender(mailbox=mailbox)
    demo = _demo(services, mailer=mailer)
    principal = services["principal"]

    demo.inject_arrivals(principal)
    demo.reset(principal)
    demo.inject_arrivals(principal)

    ids = [m["message_id"] for m in mailer.sent]
    assert len(set(ids)) == 2  # unique identifiers even across a reset
