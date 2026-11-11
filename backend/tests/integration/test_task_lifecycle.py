"""Task lifecycle integration tests against a real SQLite database."""
from __future__ import annotations

from datetime import date

import pytest

from app.application.commands import (
    CreateTaskCommand,
    ListTasksQuery,
    UpdateTaskCommand,
)
from app.domain.shared.errors import AuthorizationError, NotFoundError
from app.domain.tasks.enums import Priority, TaskStatus, Urgency


def test_create_and_get_task(services):
    dto = services["tasks"].create_task(
        services["principal"],
        CreateTaskCommand(title="Review docs", category="Maintenance", due_date=date(2026, 3, 10)),
    )
    assert dto.title == "Review docs"
    assert dto.status is TaskStatus.OPEN
    assert dto.urgency is Urgency.DUE  # due today
    fetched = services["tasks"].get_task(services["principal"], dto.id)
    assert fetched.id == dto.id


def test_create_normalizes_title_and_category(services):
    dto = services["tasks"].create_task(
        services["principal"],
        CreateTaskCommand(title="  spaced   title  ", category="  Flight   Admin "),
    )
    assert dto.title == "spaced title"
    assert dto.category == "Flight Admin"


def test_update_task_and_clear_due_date(services):
    dto = services["tasks"].create_task(
        services["principal"],
        CreateTaskCommand(title="T", category="General", due_date=date(2026, 3, 20)),
    )
    updated = services["tasks"].update_task(
        services["principal"],
        dto.id,
        UpdateTaskCommand(title="T2", priority=Priority.HIGH, due_date_provided=True, due_date=None),
    )
    assert updated.title == "T2"
    assert updated.priority is Priority.HIGH
    assert updated.due_date is None
    assert updated.urgency is Urgency.NORMAL


def test_complete_preserves_history_and_is_idempotent(services):
    dto = services["tasks"].create_task(
        services["principal"], CreateTaskCommand(title="Done soon", category="General")
    )
    completed = services["tasks"].complete_task(services["principal"], dto.id)
    assert completed.status is TaskStatus.COMPLETED
    assert completed.completed_at is not None
    # idempotent: second completion returns unchanged, no new occurrence
    again = services["tasks"].complete_task(services["principal"], dto.id)
    assert again.completed_at == completed.completed_at
    assert again.occurrence_number == completed.occurrence_number
    # completed task no longer in the active set
    active = services["tasks"].list_tasks(services["principal"], ListTasksQuery(status="open"))
    assert all(t.id != dto.id for t in active)
    # but present in the all-status view
    everything = services["tasks"].list_tasks(services["principal"], ListTasksQuery(status="all"))
    assert any(t.id == dto.id for t in everything)


def test_reopen_returns_task_to_active_set(services):
    dto = services["tasks"].create_task(
        services["principal"], CreateTaskCommand(title="Reopen me", category="General")
    )
    services["tasks"].complete_task(services["principal"], dto.id)
    reopened = services["tasks"].reopen_task(services["principal"], dto.id)
    assert reopened.status is TaskStatus.OPEN
    assert reopened.completed_at is None


def test_delete_removes_task(services):
    dto = services["tasks"].create_task(
        services["principal"], CreateTaskCommand(title="Delete me", category="General")
    )
    services["tasks"].delete_task(services["principal"], dto.id)
    with pytest.raises(NotFoundError):
        services["tasks"].get_task(services["principal"], dto.id)


def test_not_found_for_unknown_task(services):
    with pytest.raises(NotFoundError):
        services["tasks"].get_task(services["principal"], "does-not-exist")


def test_viewer_cannot_create_task(services, viewer):
    with pytest.raises(AuthorizationError):
        services["tasks"].create_task(viewer, CreateTaskCommand(title="X", category="General"))


def test_viewer_can_read_tasks(services, viewer):
    services["tasks"].create_task(
        services["principal"], CreateTaskCommand(title="Visible", category="General")
    )
    # viewer has tasks:read; owner scoping means they see only their own (none)
    items = services["tasks"].list_tasks(viewer, ListTasksQuery(status="all"))
    assert items == []


def test_owner_scoping_hides_other_operators_tasks(services, viewer):
    dto = services["tasks"].create_task(
        services["principal"], CreateTaskCommand(title="Maverick only", category="General")
    )
    with pytest.raises(NotFoundError):
        services["tasks"].get_task(viewer, dto.id)
