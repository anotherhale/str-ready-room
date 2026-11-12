"""Integration tests for the calendar service against the real SQLAlchemy cache.

The provider is a genuine second adapter (``InMemoryCalendarProvider``), not a
mock of the service's own collaborators; persistence is the real adapter.
"""
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.application.commands import CalendarEventCreateCommand, CaptureCalendarEventCommand
from app.application.services.calendar_service import CalendarService
from app.calendar.domain import CalendarEvent
from app.calendar.providers.base import CalendarError
from app.domain.shared.errors import AuthorizationError
from tests.doubles import InMemoryCalendarProvider

ZONE = ZoneInfo("America/New_York")


@pytest.fixture
def provider() -> InMemoryCalendarProvider:
    return InMemoryCalendarProvider()


@pytest.fixture
def calendar(services, provider):
    return CalendarService(
        services["database"],
        services["authorizer"],
        services["clock"],
        services["ids"],
        provider=provider,
        default_calendar="detachment",
    )


def _event(uid: str, *, day: int, hour: int = 9, minute: int = 0) -> CalendarEvent:
    start = datetime.combine(date(2026, 3, day), time(hour, minute), tzinfo=ZONE)
    return CalendarEvent(
        uid=uid,
        calendar_id="detachment",
        summary=f"Event {uid}",
        start=start,
        end=start.replace(hour=hour + 1) if hour < 23 else None,
        updated_at=datetime(2026, 3, 10, 13, 0, 0),
    )


def test_sync_populates_cache(calendar, provider, services):
    provider.seed(_event("e1", day=10))
    provider.seed(_event("e2", day=11))

    result = calendar.sync(services["principal"])

    assert result.fetched == 2
    assert result.created == 2
    assert result.updated == 0
    agenda = calendar.agenda(services["principal"], days=7)
    assert {e.uid for e in agenda.events} == {"e1", "e2"}
    assert agenda.available is True


def test_sync_is_idempotent_and_preserves_capture_link(calendar, provider, services):
    provider.seed(_event("e1", day=10))
    calendar.sync(services["principal"])
    cached = calendar.agenda(services["principal"], days=7).events[0]

    task = calendar.capture_event(
        services["principal"], CaptureCalendarEventCommand(event_id=cached.id)
    )
    assert task.title == "Event e1"

    # Re-syncing must update in place, not delete/re-insert, and keep the link.
    second = calendar.sync(services["principal"])
    assert second.created == 0
    assert second.updated == 1
    assert second.pruned == 0
    refreshed = calendar.agenda(services["principal"], days=7).events[0]
    assert refreshed.task_id == task.id
    assert refreshed.captured is True


def test_sync_prunes_events_removed_at_provider(calendar, provider, services):
    provider.seed(_event("e1", day=10))
    provider.seed(_event("e2", day=11))
    calendar.sync(services["principal"])

    provider.delete_event("detachment", "e2")
    result = calendar.sync(services["principal"])

    assert result.pruned == 1
    assert {e.uid for e in calendar.agenda(services["principal"], days=7).events} == {"e1"}


def test_capture_is_idempotent(calendar, provider, services):
    provider.seed(_event("e1", day=10))
    calendar.sync(services["principal"])
    cached = calendar.agenda(services["principal"], days=7).events[0]

    first = calendar.capture_event(services["principal"], CaptureCalendarEventCommand(event_id=cached.id))
    second = calendar.capture_event(services["principal"], CaptureCalendarEventCommand(event_id=cached.id))

    assert first.id == second.id
    # Exactly one task exists for the event.
    from app.application.commands import ListTasksQuery

    tasks = services["tasks"].list_tasks(services["principal"], ListTasksQuery(status="all"))
    assert sum(1 for t in tasks if t.id == first.id) == 1


def test_capture_uses_local_date_and_digest(calendar, provider, services):
    provider.seed(_event("e1", day=10, hour=7, minute=30))
    calendar.sync(services["principal"])
    cached = calendar.agenda(services["principal"], days=7).events[0]

    task = calendar.capture_event(
        services["principal"],
        CaptureCalendarEventCommand(event_id=cached.id, category="Flight Administration"),
    )
    assert task.due_date == date(2026, 3, 10)
    assert task.category == "Flight Administration"
    assert "From calendar" in (task.description or "")


def test_create_event_caches_under_canonical_id(calendar, provider, services):
    created = calendar.create_event(
        services["principal"],
        CalendarEventCreateCommand(
            summary="Tow bar window",
            start=datetime.combine(date(2026, 3, 12), time(13, 0), tzinfo=ZONE),
            end=datetime.combine(date(2026, 3, 12), time(14, 0), tzinfo=ZONE),
        ),
    )
    assert created.calendar_id == "/detachment/"

    # A later sync sees the same provider event and must update, not duplicate.
    result = calendar.sync(services["principal"])
    assert result.fetched == 1
    assert result.updated == 1
    assert result.created == 0
    assert len(calendar.agenda(services["principal"], days=7).events) == 1


def test_create_event_anchors_floating_local_time_to_operator_zone(calendar, services):
    # The UI's datetime-local control sends a naive wall-clock time. It must be
    # anchored to the operator's zone, not stored/returned as ambiguous or as
    # UTC — otherwise the browser re-interprets it and the displayed time drifts
    # (regression: 16:00 entered showed as 18:00).
    created = calendar.create_event(
        services["principal"],
        CalendarEventCreateCommand(
            summary="Floating local time",
            start=datetime(2026, 3, 12, 16, 0),
            end=datetime(2026, 3, 12, 17, 0),
        ),
    )
    # The principal's zone is America/New_York (conftest); the wall clock must
    # survive and the value must be unambiguous (offset-bearing).
    assert created.start.tzinfo is not None
    assert created.start.utcoffset() is not None
    assert created.start.hour == 16
    assert created.start.utcoffset().total_seconds() == -4 * 3600  # EDT on 2026-03-12


def test_create_event_preserves_aware_time(calendar, services):
    aware = datetime.combine(date(2026, 3, 12), time(16, 0), tzinfo=ZONE)
    created = calendar.create_event(
        services["principal"],
        CalendarEventCreateCommand(summary="Aware time", start=aware),
    )
    assert created.start == aware


def test_agenda_window_excludes_far_future(calendar, provider, services):
    provider.seed(_event("near", day=10))
    provider.seed(_event("far", day=25))
    calendar.sync(services["principal"])

    agenda = calendar.agenda(services["principal"], days=7)
    assert {e.uid for e in agenda.events} == {"near"}


def test_unavailable_provider_reports_detail(services):
    from app.application.services.calendar_service import CalendarService

    service = CalendarService(
        services["database"], services["authorizer"], services["clock"], services["ids"], provider=None
    )
    agenda = service.agenda(services["principal"])
    assert agenda.available is False
    assert agenda.detail is not None
    status = service.status(services["principal"])
    assert status.available is False


def test_sync_without_provider_raises(services):
    from app.application.services.calendar_service import CalendarService

    service = CalendarService(
        services["database"], services["authorizer"], services["clock"], services["ids"], provider=None
    )
    with pytest.raises(CalendarError):
        service.sync(services["principal"])


def test_viewer_cannot_sync(calendar, provider, services, viewer):
    with pytest.raises(AuthorizationError):
        calendar.sync(viewer)


def test_quiet_sync_swallows_provider_failure(calendar, provider, services):
    provider.set_reachable(False)
    assert calendar.sync_quietly(services["principal"]) is False


def test_delete_event_removes_from_cache_and_provider(calendar, provider, services):
    provider.seed(_event("e1", day=10))
    calendar.sync(services["principal"])
    cached = calendar.agenda(services["principal"], days=7).events[0]

    calendar.delete_event(services["principal"], cached.id)

    assert calendar.agenda(services["principal"], days=7).events == []
    assert provider.list_events("detachment") == []
