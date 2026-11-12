"""API integration tests for the calendar and mailbox endpoints.

Runs the real FastAPI app and real adapters.  After startup the container's
calendar/mailbox services are re-pointed at the in-memory providers (genuine
second adapters) so the HTTP surface can be exercised end to end without an
external CalDAV/IMAP server.
"""
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.application.services.calendar_service import CalendarService
from app.application.services.email_service import EmailService
from app.calendar.domain import CalendarEvent
from app.config import Settings
from tests.doubles import InMemoryCalendarProvider, InMemoryMailboxProvider

ZONE = ZoneInfo("America/New_York")


@pytest.fixture
def providers():
    return InMemoryCalendarProvider(), InMemoryMailboxProvider()


@pytest.fixture
def client(tmp_path, monkeypatch, providers):
    calendar_provider, mailbox_provider = providers
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/api_integration.db",
        operator_id="maverick",
        operator_display_name="Maverick",
        default_timezone="America/New_York",
        seed_on_startup=True,
        fixed_now_utc="2026-03-10T13:00:00",
        # Disable real providers at startup so the app boots without them...
        calendar_provider="none",
        email_provider="none",
    )
    import app.config as config_module
    import app.main as main_module

    monkeypatch.setattr(config_module, "get_settings", lambda: settings)
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)

    app = main_module.create_app()
    with TestClient(app) as test_client:
        container = test_client.app.state.container
        # ...then swap in the in-memory providers for the test.
        container.calendar = CalendarService(
            container.database, container.authorizer, container.clock, container.ids,
            provider=calendar_provider, default_calendar="detachment",
        )
        container.email = EmailService(
            container.database, container.authorizer, container.clock, container.ids,
            provider=mailbox_provider, mailbox_name="INBOX",
        )
        yield test_client


def _seed_calendar_event(provider: InMemoryCalendarProvider, uid: str = "e1", day: int = 10) -> None:
    start = datetime.combine(date(2026, 3, day), time(7, 30), tzinfo=ZONE)
    provider.seed(
        CalendarEvent(
            uid=uid,
            calendar_id="detachment",
            summary="Detachment flight quarters",
            start=start,
            end=start.replace(hour=8, minute=15),
            location="Ready room",
            updated_at=datetime(2026, 3, 10, 13, 0, 0),
        )
    )


# -- calendar -------------------------------------------------------------
def test_calendar_status_reports_available(client):
    resp = client.get("/api/calendar/status")
    assert resp.status_code == 200
    assert resp.json()["available"] is True


def test_calendar_sync_then_agenda(client, providers):
    provider, _ = providers
    _seed_calendar_event(provider)

    sync = client.post("/api/calendar/sync")
    assert sync.status_code == 200, sync.text
    assert sync.json()["created"] == 1

    agenda = client.get("/api/calendar/agenda")
    assert agenda.status_code == 200
    body = agenda.json()
    assert body["available"] is True
    assert len(body["events"]) == 1
    assert body["events"][0]["summary"] == "Detachment flight quarters"
    assert body["events"][0]["captured"] is False


def test_calendar_create_event_and_delete(client):
    create = client.post(
        "/api/calendar/events",
        json={
            "summary": "Tow bar window",
            "start": "2026-03-12T13:00:00-05:00",
            "end": "2026-03-12T14:00:00-05:00",
        },
    )
    assert create.status_code == 201, create.text
    event_id = create.json()["id"]

    agenda = client.get("/api/calendar/agenda").json()
    assert any(e["id"] == event_id for e in agenda["events"])

    delete = client.delete(f"/api/calendar/events/{event_id}")
    assert delete.status_code == 204
    agenda_after = client.get("/api/calendar/agenda").json()
    assert all(e["id"] != event_id for e in agenda_after["events"])


def test_calendar_capture_creates_task_and_marks_event(client, providers):
    provider, _ = providers
    _seed_calendar_event(provider)
    client.post("/api/calendar/sync")
    event = client.get("/api/calendar/agenda").json()["events"][0]

    capture = client.post(
        f"/api/calendar/events/{event['id']}/tasks",
        json={"category": "Flight Administration"},
    )
    assert capture.status_code == 201, capture.text
    task = capture.json()
    assert task["title"] == "Detachment flight quarters"
    assert task["due_date"] == "2026-03-10"

    # Idempotent: capturing again returns the same task.
    again = client.post(f"/api/calendar/events/{event['id']}/tasks", json={})
    assert again.status_code == 201
    assert again.json()["id"] == task["id"]

    # The event now reports as captured.
    refreshed = client.get("/api/calendar/agenda").json()["events"][0]
    assert refreshed["captured"] is True
    assert refreshed["task_id"] == task["id"]


def test_calendar_sync_unavailable_returns_502(client):
    container = client.app.state.container
    container.calendar = CalendarService(
        container.database, container.authorizer, container.clock, container.ids, provider=None
    )
    resp = client.post("/api/calendar/sync")
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "unavailable"


# -- email ----------------------------------------------------------------
def test_mail_list_and_read(client, providers):
    _, mailbox = providers
    mailbox.add(message_id="<m1@x>", subject="Tow bar inspection", body="Confirm the window.")

    listed = client.get("/api/mail/messages")
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["subject"] == "Tow bar inspection"
    assert listed.json()[0]["captured"] is False

    message = client.get("/api/mail/messages/%3Cm1@x%3E")
    assert message.status_code == 200
    assert message.json()["body"] == "Confirm the window."


def test_mail_capture_creates_task(client, providers):
    _, mailbox = providers
    mailbox.add(message_id="<m1@x>", subject="Tow bar inspection", body="Confirm the window.")

    capture = client.post(
        "/api/mail/messages/%3Cm1@x%3E/tasks",
        json={"category": "Maintenance", "due_date": "2026-03-12"},
    )
    assert capture.status_code == 201, capture.text
    task = capture.json()
    assert task["title"] == "Tow bar inspection"
    assert task["category"] == "Maintenance"

    # Idempotent.
    again = client.post("/api/mail/messages/%3Cm1@x%3E/tasks", json={})
    assert again.json()["id"] == task["id"]

    listed = client.get("/api/mail/messages").json()
    assert listed[0]["captured"] is True


def test_mail_unavailable_returns_502(client):
    container = client.app.state.container
    container.email = EmailService(
        container.database, container.authorizer, container.clock, container.ids, provider=None
    )
    resp = client.get("/api/mail/messages")
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "unavailable"


def test_mail_status(client, providers):
    _, mailbox = providers
    mailbox.add(message_id="<m1@x>")
    resp = client.get("/api/mail/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["message_count"] == 1
