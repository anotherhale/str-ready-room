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


def _wired_demo(services, seed, calendar):
    """A DemoService with the integrations wired, as composition does."""
    from app.application.services.demo_service import DemoService

    return DemoService(
        services["database"],
        services["authorizer"],
        services["clock"],
        services["ids"],
        integration_seed=seed,
        calendar=calendar,
    )


def test_reset_reseeds_calendar_and_refreshes_cache(services, calendar_provider):
    """A reset must leave the Calendar view populated, not blank (D-034)."""
    from app.application.services.calendar_service import CalendarService

    principal = services["principal"]
    calendar = CalendarService(
        services["database"], services["authorizer"], services["clock"], services["ids"],
        provider=calendar_provider, default_calendar="detachment",
    )
    mailer = RecordingMailSender()
    seed = IntegrationSeedService(
        services["database"], services["clock"],
        calendar_provider=calendar_provider, default_calendar="detachment", mail_sender=mailer,
    )
    demo = _wired_demo(services, seed, calendar)

    demo.reset(principal)

    # The provider is reseeded and the cache is refreshed in the same call.
    assert len(calendar_provider.list_events("detachment")) == 4
    assert len(calendar.agenda(principal).events) >= 1
    assert seed._marker(principal, "calendar_seed_version") >= 1


def test_reset_reseeds_mailbox(services):
    """A reset must restore the demo mailbox messages (D-034)."""
    mailbox = InMemoryMailboxProvider()
    mailer = RecordingMailSender(mailbox=mailbox)
    seed = IntegrationSeedService(
        services["database"], services["clock"], mail_sender=mailer, mailbox_provider=mailbox
    )
    demo = _wired_demo(services, seed, None)
    principal = services["principal"]

    demo.reset(principal)

    assert len(mailer.sent) == 3
    assert len(mailbox.list_messages()) == 3


def test_reset_does_not_duplicate_mail_already_in_server(services):
    """A reset must leave exactly the three demo messages, never duplicates.

    Reset now purges the mailbox first (D-040), then reseeds, so the demo
    messages are re-delivered to a clean mailbox.  The invariant is the mailbox
    *contents*: exactly the three demo messages, never 3 + 3.
    """
    mailbox = InMemoryMailboxProvider()
    mailer = RecordingMailSender(mailbox=mailbox)
    seed = IntegrationSeedService(
        services["database"], services["clock"], mail_sender=mailer, mailbox_provider=mailbox
    )
    demo = _wired_demo(services, seed, None)
    principal = services["principal"]

    seed.seed_mailbox_if_needed(principal)
    assert len(mailbox.list_messages()) == 3

    demo.reset(principal)

    # No duplicates: still exactly the three demo messages, even though the
    # reset re-delivered them after purging.
    assert len(mailbox.list_messages()) == 3
    assert len(mailer.sent) == 6


def test_reset_without_integrations_is_unaffected(services):
    """The base stack (no providers) resets exactly as before."""
    principal = services["principal"]
    services["demo"].reset(principal)  # no integration_seed/calendar wired
    # Core data is reseeded as usual.
    from app.application.ports.persistence import TaskQuery

    with services["database"].create() as uow:
        tasks = uow.tasks.list(TaskQuery(), principal.id)
    assert len(tasks) > 0


def test_calendar_seed_reconciles_against_persistent_provider(seed, services, calendar_provider):
    """A fresh application DB with a persistent provider must not fail seeding.

    After a reset (or a DB wipe) the marker is cleared, but the provider still
    holds the demo events.  The seeder must detect that and set the marker,
    rather than treating the create conflict as "provider unavailable".
    """
    principal = services["principal"]
    assert seed.seed_calendar_if_needed(principal) is True
    assert len(calendar_provider.list_events("detachment")) == 4

    # Simulate a fresh marker (reset / DB wipe) while the provider keeps its data.
    seed._set_marker(principal, "calendar_seed_version", 0)

    assert seed.seed_calendar_if_needed(principal) is True
    # Still exactly the four demo events — no duplicates, no spurious failure.
    assert len(calendar_provider.list_events("detachment")) == 4


# -- clear_demo_data + reset clears the providers (D-040) -------------------


def _wired_demo_with_providers(services, calendar_provider, mailbox, mailer):
    """A DemoService with both providers and the seeder wired, as composition does."""
    from app.application.services.calendar_service import CalendarService

    calendar = CalendarService(
        services["database"], services["authorizer"], services["clock"], services["ids"],
        provider=calendar_provider, default_calendar="detachment",
    )
    seed = IntegrationSeedService(
        services["database"], services["clock"],
        calendar_provider=calendar_provider, default_calendar="detachment",
        mail_sender=mailer, mailbox_provider=mailbox,
    )
    return _wired_demo(services, seed, calendar), calendar, seed


def test_clear_demo_data_empties_both_providers(services, calendar_provider):
    mailbox = InMemoryMailboxProvider()
    mailer = RecordingMailSender(mailbox=mailbox)
    demo, _calendar, seed = _wired_demo_with_providers(services, calendar_provider, mailbox, mailer)
    principal = services["principal"]

    seed.seed_calendar_if_needed(principal)
    seed.seed_mailbox_if_needed(principal)
    assert len(mailbox.list_messages()) == 3
    assert len(calendar_provider.list_events("detachment")) == 4

    messages_removed, events_removed = seed.clear_demo_data(principal)

    assert messages_removed == 3
    assert events_removed == 4
    assert mailbox.list_messages() == []
    assert calendar_provider.list_events("detachment") == []


def test_clear_demo_data_is_idempotent(services, calendar_provider):
    mailbox = InMemoryMailboxProvider()
    mailer = RecordingMailSender(mailbox=mailbox)
    _demo, _calendar, seed = _wired_demo_with_providers(services, calendar_provider, mailbox, mailer)
    principal = services["principal"]

    # Nothing seeded yet: clearing an empty provider is a no-op, not an error.
    assert seed.clear_demo_data(principal) == (0, 0)
    assert seed.clear_demo_data(principal) == (0, 0)


def test_clear_demo_data_survives_unreachable_providers(services, calendar_provider):
    mailbox = InMemoryMailboxProvider()
    mailer = RecordingMailSender(mailbox=mailbox)
    _demo, _calendar, seed = _wired_demo_with_providers(services, calendar_provider, mailbox, mailer)
    principal = services["principal"]

    seed.seed_calendar_if_needed(principal)
    seed.seed_mailbox_if_needed(principal)
    calendar_provider.set_reachable(False)
    mailbox.set_reachable(False)

    # A provider outage must not raise out of a reset: the channel is skipped.
    assert seed.clear_demo_data(principal) == (0, 0)


def test_reset_removes_injected_arrivals_and_restores_demo_state(services, calendar_provider):
    """The defect this change fixes: injected arrivals must not survive a reset.

    Simulate two live arrivals (two extra messages, two extra events), then
    reset.  The providers must return to exactly the demo baseline (3 messages,
    4 events) rather than accumulating the arrivals.
    """
    from datetime import datetime

    from app.application.commands import CalendarEventCreateCommand

    mailbox = InMemoryMailboxProvider()
    mailer = RecordingMailSender(mailbox=mailbox)
    demo, calendar, seed = _wired_demo_with_providers(services, calendar_provider, mailbox, mailer)
    principal = services["principal"]

    # Baseline demo state.
    demo.reset(principal)
    assert len(mailbox.list_messages()) == 3
    assert len(calendar_provider.list_events("detachment")) == 4

    # Two live arrivals: each delivers one message and one event.
    for i in range(2):
        mailer.send(
            sender="ops@detachment.demo", recipient="maverick@detachment.demo",
            subject=f"arrival {i}", body="b", message_id=f"<arrival-{i}@demo>",
        )
        calendar.create_event(
            principal,
            CalendarEventCreateCommand(
                summary=f"arrival {i}",
                start=datetime(2026, 3, 12, 10, 0),
                end=datetime(2026, 3, 12, 10, 30),
            ),
        )
    assert len(mailbox.list_messages()) == 5
    assert len(calendar_provider.list_events("detachment")) == 6

    result = demo.reset(principal)

    # Providers are back to the demo baseline — no accumulated arrivals.
    assert len(mailbox.list_messages()) == 3
    assert len(calendar_provider.list_events("detachment")) == 4
    # The reset reports what it cleared.
    assert result.mailbox_cleared == 5
    assert result.calendar_cleared == 6


def test_reset_is_stable_across_repeated_resets_with_arrivals(services, calendar_provider):
    """Repeated reset-with-arrivals cycles must not grow the provider state."""
    mailbox = InMemoryMailboxProvider()
    mailer = RecordingMailSender(mailbox=mailbox)
    demo, _calendar, _seed = _wired_demo_with_providers(services, calendar_provider, mailbox, mailer)
    principal = services["principal"]

    for cycle in range(3):
        demo.reset(principal)
        mailer.send(
            sender="ops@detachment.demo", recipient="maverick@detachment.demo",
            subject=f"c{cycle}", body="b", message_id=f"<c{cycle}@demo>",
        )
        assert len(mailbox.list_messages()) == 4

    demo.reset(principal)
    assert len(mailbox.list_messages()) == 3
    assert len(calendar_provider.list_events("detachment")) == 4
