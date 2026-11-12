"""Integration tests for the mailbox service against the real SQLAlchemy store.

The provider is a genuine second adapter (``InMemoryMailboxProvider``), so the
service is exercised on real code paths with real persistence.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.application.commands import CaptureEmailCommand, ListTasksQuery
from app.application.services.email_service import EmailService
from app.domain.shared.errors import AuthorizationError
from app.mailbox.providers.base import MailboxError
from tests.doubles import InMemoryMailboxProvider


@pytest.fixture
def provider() -> InMemoryMailboxProvider:
    return InMemoryMailboxProvider()


@pytest.fixture
def email(services, provider):
    return EmailService(
        services["database"],
        services["authorizer"],
        services["clock"],
        services["ids"],
        provider=provider,
        mailbox_name="INBOX",
    )


def test_list_messages_marks_captured(services, provider, email):
    provider.add(message_id="<m1@x>", subject="First")
    provider.add(message_id="<m2@x>", subject="Second")

    listed = email.list_messages(services["principal"])
    assert [m.subject for m in listed] == ["Second", "First"]
    assert all(m.captured is False for m in listed)

    email.capture_message(services["principal"], CaptureEmailCommand(message_id="<m2@x>"))
    relisted = email.list_messages(services["principal"])
    captured = {m.message_id: m.captured for m in relisted}
    assert captured["<m2@x>"] is True
    assert captured["<m1@x>"] is False


def test_read_message_includes_body(services, provider, email):
    provider.add(message_id="<m1@x>", subject="Work order", body="Please sign.")
    message = email.get_message(services["principal"], "<m1@x>")
    assert message.subject == "Work order"
    assert message.body == "Please sign."
    assert message.captured is False


def test_capture_creates_task_with_provenance(services, provider, email):
    provider.add(
        message_id="<m1@x>",
        subject="Tow bar inspection",
        body="Confirm the window.",
        received_at=datetime(2026, 3, 10, 9, 0, 0),
    )
    task = email.capture_message(
        services["principal"],
        CaptureEmailCommand(message_id="<m1@x>", category="Maintenance", due_date=date(2026, 3, 12)),
    )
    assert task.title == "Tow bar inspection"
    assert task.category == "Maintenance"
    assert task.due_date == date(2026, 3, 12)
    assert "Captured from email" in (task.description or "")
    assert "Confirm the window." in (task.description or "")


def test_capture_is_idempotent(services, provider, email):
    provider.add(message_id="<m1@x>", subject="Only once")
    first = email.capture_message(services["principal"], CaptureEmailCommand(message_id="<m1@x>"))
    second = email.capture_message(services["principal"], CaptureEmailCommand(message_id="<m1@x>"))
    assert first.id == second.id

    tasks = services["tasks"].list_tasks(services["principal"], ListTasksQuery(status="all"))
    assert sum(1 for t in tasks if t.id == first.id) == 1


def test_recapture_reuses_single_source_row(services, provider, email):
    provider.add(message_id="<m1@x>", subject="Again")
    email.capture_message(services["principal"], CaptureEmailCommand(message_id="<m1@x>"))
    email.capture_message(services["principal"], CaptureEmailCommand(message_id="<m1@x>"))

    with services["database"].create() as uow:
        sources = uow.email_sources.list(services["principal"].id)
    assert len(sources) == 1


def test_status_reports_counts(services, provider, email):
    provider.add(message_id="<m1@x>")
    provider.add(message_id="<m2@x>")
    email.capture_message(services["principal"], CaptureEmailCommand(message_id="<m1@x>"))

    status = email.status(services["principal"])
    assert status.available is True
    assert status.message_count == 2
    assert status.captured_count == 1


def test_status_reports_unavailable_when_provider_offline(services, provider, email):
    provider.set_reachable(False)
    status = email.status(services["principal"])
    assert status.available is False
    assert status.detail is not None


def test_list_without_provider_raises(services):
    service = EmailService(
        services["database"], services["authorizer"], services["clock"], services["ids"], provider=None
    )
    with pytest.raises(MailboxError):
        service.list_messages(services["principal"])


def test_capture_unknown_message_raises(services, provider, email):
    with pytest.raises(MailboxError):
        email.capture_message(services["principal"], CaptureEmailCommand(message_id="<missing@x>"))


def test_viewer_cannot_capture(services, provider, email, viewer):
    provider.add(message_id="<m1@x>")
    with pytest.raises(AuthorizationError):
        email.capture_message(viewer, CaptureEmailCommand(message_id="<m1@x>"))
