"""Task aggregate lifecycle tests (pure domain, no database)."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.domain.shared.errors import ValidationError
from app.domain.tasks.entities import Task
from app.domain.tasks.enums import Priority, TaskStatus

NOW = datetime(2026, 3, 10, 9, 0, 0)
LATER = datetime(2026, 3, 10, 17, 0, 0)


def make_task(**overrides) -> Task:
    base = {
        "id": "t1",
        "owner_id": "op-1",
        "title": "Review maintenance documentation",
        "category": "Maintenance",
        "now": NOW,
        "due_date": date(2026, 3, 10),
    }
    base.update(overrides)
    return Task.create(**base)


def test_create_sets_timestamps_and_defaults():
    task = make_task()
    assert task.status is TaskStatus.OPEN
    assert task.priority is Priority.NORMAL
    assert task.created_at == NOW
    assert task.updated_at == NOW
    assert task.occurrence_number == 1
    assert task.is_open


def test_title_is_normalized_and_required():
    assert make_task(title="  spaced   out  ").title == "spaced out"
    with pytest.raises(ValidationError):
        make_task(title="   ")


def test_complete_is_idempotent():
    task = make_task()
    assert task.complete(LATER) is True
    assert task.is_completed
    assert task.completed_at == LATER
    # second completion returns unchanged
    assert task.complete(datetime(2026, 3, 11)) is False
    assert task.completed_at == LATER


def test_reopen_clears_completed_at():
    task = make_task()
    task.complete(LATER)
    assert task.reopen(datetime(2026, 3, 11)) is True
    assert task.is_open
    assert task.completed_at is None
    # reopening an already-open task is a no-op
    assert task.reopen(datetime(2026, 3, 12)) is False


def test_update_distinguishes_clear_from_leave():
    task = make_task(description="original")
    task.update(LATER, description=None, description_provided=False)
    assert task.description == "original"  # untouched
    task.update(LATER, description=None, description_provided=True)
    assert task.description is None  # cleared
    task.update(LATER, due_date=None, due_date_provided=True)
    assert task.due_date is None


def test_update_changes_priority_and_category():
    task = make_task()
    task.update(LATER, priority=Priority.CRITICAL, category="Personnel")
    assert task.priority is Priority.CRITICAL
    assert task.category == "Personnel"


def test_occurrence_number_must_be_positive():
    with pytest.raises(ValidationError):
        Task(
            id="t",
            owner_id="o",
            title="x",
            category="General",
            created_at=NOW,
            updated_at=NOW,
            occurrence_number=0,
        )


def test_events_are_recorded_and_drained():
    task = make_task()
    task.complete(LATER)
    events = task.drain_events()
    names = [type(e).__name__ for e in events]
    assert "TaskCreated" in names
    assert "TaskCompleted" in names
    assert task.drain_events() == []
