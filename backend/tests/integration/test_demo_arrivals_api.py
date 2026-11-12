"""API tests for the live demo arrival endpoint (D-039).

Runs the real FastAPI app.  After startup the container's calendar/mailbox
services *and* the demo service are re-pointed at in-memory providers (genuine
second adapters) so the HTTP surface is exercised end to end without an external
CalDAV/IMAP server.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.application.ports.mail import MailSender
from app.application.services.calendar_service import CalendarService
from app.application.services.demo_service import DemoService
from app.application.services.email_service import EmailService
from app.config import Settings
from tests.doubles import InMemoryCalendarProvider, InMemoryMailboxProvider


class RecordingMailSender(MailSender):
    """A genuine ``MailSender`` that delivers into an in-memory mailbox."""

    def __init__(self, mailbox: InMemoryMailboxProvider) -> None:
        self.sent: list[str] = []
        self._mailbox = mailbox

    def send(self, *, sender: str, recipient: str, subject: str, body: str, message_id: str) -> None:
        self.sent.append(message_id)
        self._mailbox.add(
            message_id=message_id, sender=sender, subject=subject, body=body,
            received_at=datetime.now(UTC),
        )


@pytest.fixture
def providers():
    return InMemoryCalendarProvider(), InMemoryMailboxProvider()


@pytest.fixture
def client(tmp_path, monkeypatch, providers):
    calendar_provider, mailbox_provider = providers
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/arrivals_api.db",
        operator_id="maverick",
        operator_display_name="Maverick",
        default_timezone="America/New_York",
        seed_on_startup=True,
        fixed_now_utc="2026-03-10T13:00:00",
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
        # Swap in the in-memory providers for the test...
        calendar = CalendarService(
            container.database, container.authorizer, container.clock, container.ids,
            provider=calendar_provider, default_calendar="detachment",
        )
        email = EmailService(
            container.database, container.authorizer, container.clock, container.ids,
            provider=mailbox_provider, mailbox_name="INBOX",
        )
        mailer = RecordingMailSender(mailbox_provider)
        container.calendar = calendar
        container.email = email
        # ...and rebuild the demo service so arrivals use those providers.
        container.demo = DemoService(
            container.database, container.authorizer, container.clock, container.ids,
            calendar=calendar, mail_sender=mailer, default_calendar="detachment",
        )
        yield test_client


def test_demo_arrivals_delivers_both_and_they_are_readable(client):
    resp = client.post("/api/demo/arrivals")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email_delivered"] is True
    assert body["calendar_delivered"] is True

    # The new message and event are immediately visible through the read APIs.
    messages = client.get("/api/mail/messages").json()
    assert len(messages) == 1
    agenda = client.get("/api/calendar/agenda").json()
    assert agenda["available"] is True
    assert len(agenda["events"]) == 1


def test_demo_arrivals_new_message_can_be_captured(client):
    client.post("/api/demo/arrivals")
    message = client.get("/api/mail/messages").json()[0]
    assert message["captured"] is False

    capture = client.post(
        f"/api/mail/messages/{message['message_id']}/tasks",
        json={"category": "Maintenance"},
    )
    assert capture.status_code == 201, capture.text
    assert capture.json()["title"] == message["subject"]


def test_demo_arrivals_is_repeatable(client):
    for _ in range(3):
        assert client.post("/api/demo/arrivals").status_code == 200
    assert len(client.get("/api/mail/messages").json()) == 3
    assert len(client.get("/api/calendar/agenda").json()["events"]) == 3


def test_demo_arrivals_degrades_when_integrations_off(client):
    """With providers swapped out, the endpoint still succeeds and reports why."""
    container = client.app.state.container
    container.demo = DemoService(
        container.database, container.authorizer, container.clock, container.ids,
    )
    resp = client.post("/api/demo/arrivals")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email_delivered"] is False
    assert body["calendar_delivered"] is False
