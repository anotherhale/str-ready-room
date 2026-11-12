"""Integration seed tests for the optional calendar and mailbox integrations.

The provider/mailer are genuine adapters (in-memory provider, recording mailer),
and persistence is the real adapter.  The focus is idempotency: repeated startup
must never duplicate demo integration data.
"""
from __future__ import annotations

import pytest

from app.application.ports.mail import MailSender
from app.application.services.integration_seed_service import (
    DEMO_RECIPIENT,
    IntegrationSeedService,
)
from tests.doubles import InMemoryCalendarProvider, InMemoryMailboxProvider


class RecordingMailSender(MailSender):
    """A genuine ``MailSender`` adapter that records instead of delivering.

    When given a ``mailbox``, delivered messages are also appended to it, so a
    test can exercise the mailbox-side reconciliation (the real GreenMail keeps
    messages in memory and loses them on restart).
    """

    def __init__(self, *, fail_times: int = 0, mailbox=None) -> None:  # noqa: ANN001
        self.sent: list[dict[str, str]] = []
        self._fail_times = fail_times
        self._mailbox = mailbox

    def send(self, *, sender: str, recipient: str, subject: str, body: str, message_id: str) -> None:
        if self._fail_times > 0:
            self._fail_times -= 1
            from app.application.ports.mail import MailSenderError

            raise MailSenderError("smtp down")
        self.sent.append(
            {"sender": sender, "recipient": recipient, "subject": subject, "message_id": message_id}
        )
        if self._mailbox is not None:
            self._mailbox.add(message_id=message_id, sender=sender, subject=subject, body=body)


@pytest.fixture
def calendar_provider() -> InMemoryCalendarProvider:
    return InMemoryCalendarProvider()


@pytest.fixture
def mailer() -> RecordingMailSender:
    return RecordingMailSender()


@pytest.fixture
def seed(services, calendar_provider, mailer):
    return IntegrationSeedService(
        services["database"],
        services["clock"],
        calendar_provider=calendar_provider,
        default_calendar="detachment",
        mail_sender=mailer,
    )


def test_mailbox_seed_repairs_after_mail_server_restart(services):
    """GreenMail keeps mail in memory; the marker must not mask an empty mailbox.

    A partial restart (persistent DB, fresh mail container) leaves the marker
    set but the mailbox empty. The seeder reconciles against the mailbox and
    reseeds, so the demo state is always restorable without duplication.
    """
    mailbox = InMemoryMailboxProvider()
    mailer = RecordingMailSender(mailbox=mailbox)
    seed = IntegrationSeedService(
        services["database"], services["clock"], mail_sender=mailer, mailbox_provider=mailbox
    )
    principal = services["principal"]

    assert seed.seed_mailbox_if_needed(principal) is True
    assert len(mailer.sent) == 3

    # A healthy, populated mailbox is left alone (marker + content both agree).
    assert seed.seed_mailbox_if_needed(principal) is False
    assert len(mailer.sent) == 3

    # Simulate the mail container losing its in-memory store.
    mailbox._messages.clear()
    assert seed.seed_mailbox_if_needed(principal) is True
    assert len(mailer.sent) == 6
    assert len(mailbox.list_messages()) == 3


def test_calendar_seed_is_idempotent(seed, services, calendar_provider):
    principal = services["principal"]
    assert seed.seed_calendar_if_needed(principal) is True
    assert len(calendar_provider.list_events("detachment")) == 4

    # Second call is a no-op because the marker is set.
    assert seed.seed_calendar_if_needed(principal) is False
    assert len(calendar_provider.list_events("detachment")) == 4


def test_calendar_seed_uses_local_wall_clock(seed, services, calendar_provider):
    seed.seed_calendar_if_needed(services["principal"])
    events = calendar_provider.list_events("detachment")
    quarters = next(e for e in events if e.uid == "demo-flight-quarters")
    local = quarters.start.astimezone(quarters.start.tzinfo)
    assert (local.hour, local.minute) == (7, 30)


def test_calendar_seed_skips_when_provider_unreachable(seed, services, calendar_provider):
    calendar_provider.set_reachable(False)
    assert seed.seed_calendar_if_needed(services["principal"]) is False
    # Marker not set, so a later attempt can still succeed.
    calendar_provider.set_reachable(True)
    assert seed.seed_calendar_if_needed(services["principal"]) is True


def test_mailbox_seed_is_idempotent(seed, services, mailer):
    principal = services["principal"]
    assert seed.seed_mailbox_if_needed(principal) is True
    assert len(mailer.sent) == 3
    assert all(m["recipient"] == DEMO_RECIPIENT for m in mailer.sent)

    assert seed.seed_mailbox_if_needed(principal) is False
    assert len(mailer.sent) == 3


def test_mailbox_seed_retries_then_gives_up(services, mailer):
    mailer._fail_times = 99  # always fails
    seed = IntegrationSeedService(
        services["database"], services["clock"], mail_sender=mailer
    )
    assert seed.seed_mailbox_if_needed(services["principal"]) is False
    assert mailer.sent == []


def test_reset_clears_integration_markers_and_cache(seed, services, calendar_provider):
    principal = services["principal"]
    seed.seed_calendar_if_needed(principal)
    # Cache an event too.
    from app.application.services.calendar_service import CalendarService

    calendar = CalendarService(
        services["database"], services["authorizer"], services["clock"], services["ids"],
        provider=calendar_provider, default_calendar="detachment",
    )
    calendar.sync(principal)
    assert len(calendar.agenda(principal).events) >= 1

    services["demo"].reset(principal)

    # The app cache is cleared, and the seed marker is reset so a fresh demo
    # can be seeded.  The external provider is intentionally untouched: reset
    # clears *application* data, not the operator's real calendar (D-025).
    assert calendar.agenda(principal).events == []
    assert seed._marker(principal, "calendar_seed_version") == 0

    # A sync repopulates the cache from the still-present provider events.
    calendar.sync(principal)
    assert len(calendar.agenda(principal).events) >= 1
