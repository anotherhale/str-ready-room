"""Recurrence integration tests: successor generation, exactly-one successor,
open-successor guard, series/history preservation, end conditions, and
transaction rollback."""
from __future__ import annotations

from datetime import date

import pytest

from app.application.commands import (
    CreateTaskCommand,
    RecurrenceInput,
    UpdateTaskCommand,
)
from app.application.ports.persistence import TaskQuery
from app.domain.tasks.enums import EndType, Frequency, TaskStatus


def _weekly(services, *, due=None, end_type=EndType.NEVER, end_count=None):
    return RecurrenceInput(
        name="Weekly brief",
        frequency=Frequency.WEEKLY,
        day_of_week=0,
        anchor_date=due or date(2026, 3, 9),  # a Monday
        end_type=end_type,
        end_count=end_count,
    )


def test_completing_recurring_task_creates_one_successor(services):
    dto = services["tasks"].create_task(
        services["principal"],
        CreateTaskCommand(title="Monday brief", category="General", due_date=date(2026, 3, 9), recurrence=_weekly(services)),
    )
    assert dto.recurrence is not None
    services["tasks"].complete_task(services["principal"], dto.id)

    with services["database"].create() as uow:
        open_tasks = uow.tasks.list(TaskQuery(status=TaskStatus.OPEN, recurrence_rule_id=dto.recurrence.rule_id), "maverick")
    assert len(open_tasks) == 1
    successor = open_tasks[0]
    assert successor.id != dto.id
    assert successor.series_id == dto.series_id
    assert successor.occurrence_number == 2
    assert successor.due_date == date(2026, 3, 16)  # next Monday


def test_completion_idempotent_no_duplicate_successor(services):
    dto = services["tasks"].create_task(
        services["principal"],
        CreateTaskCommand(title="Monday brief", category="General", due_date=date(2026, 3, 9), recurrence=_weekly(services)),
    )
    services["tasks"].complete_task(services["principal"], dto.id)
    services["tasks"].complete_task(services["principal"], dto.id)  # idempotent

    with services["database"].create() as uow:
        all_tasks = uow.tasks.list(TaskQuery(include_all_statuses=True), "maverick")
    series = [t for t in all_tasks if t.series_id == dto.series_id]
    assert len(series) == 2  # the completed original + exactly one successor


def test_completing_successor_does_not_duplicate_open_occurrence(services):
    dto = services["tasks"].create_task(
        services["principal"],
        CreateTaskCommand(title="Monday brief", category="General", due_date=date(2026, 3, 9), recurrence=_weekly(services)),
    )
    services["tasks"].complete_task(services["principal"], dto.id)

    with services["database"].create() as uow:
        successor = uow.tasks.find_open_by_recurrence_rule(dto.recurrence.rule_id, "maverick")
    # Complete the successor: now the third occurrence is created, and there is
    # still exactly one open occurrence.
    services["tasks"].complete_task(services["principal"], successor.id)
    with services["database"].create() as uow:
        open_now = uow.tasks.list(TaskQuery(status=TaskStatus.OPEN, recurrence_rule_id=dto.recurrence.rule_id), "maverick")
    assert len(open_now) == 1
    assert open_now[0].occurrence_number == 3


def test_end_count_stops_generation(services):
    dto = services["tasks"].create_task(
        services["principal"],
        CreateTaskCommand(
            title="Two only",
            category="General",
            due_date=date(2026, 3, 9),
            recurrence=_weekly(services, end_type=EndType.COUNT, end_count=2),
        ),
    )
    services["tasks"].complete_task(services["principal"], dto.id)  # creates occurrence 2
    with services["database"].create() as uow:
        occ2 = uow.tasks.find_open_by_recurrence_rule(dto.recurrence.rule_id, "maverick")
    services["tasks"].complete_task(services["principal"], occ2.id)  # count exhausted -> no occ3
    with services["database"].create() as uow:
        open_now = uow.tasks.list(TaskQuery(status=TaskStatus.OPEN, recurrence_rule_id=dto.recurrence.rule_id), "maverick")
        rule = uow.recurrence_rules.get_by_id(dto.recurrence.rule_id, "maverick")
    assert open_now == []
    assert rule.active is False


def test_end_date_stops_generation(services):
    dto = services["tasks"].create_task(
        services["principal"],
        CreateTaskCommand(
            title="Until date",
            category="General",
            due_date=date(2026, 3, 9),
            recurrence=RecurrenceInput(
                name="Daily", frequency=Frequency.DAILY, anchor_date=date(2026, 3, 9),
                end_type=EndType.ON_DATE, end_date=date(2026, 3, 10),
            ),
        ),
    )
    services["tasks"].complete_task(services["principal"], dto.id)  # creates 3/10
    with services["database"].create() as uow:
        occ = uow.tasks.find_open_by_recurrence_rule(dto.recurrence.rule_id, "maverick")
    assert occ.due_date == date(2026, 3, 10)
    services["tasks"].complete_task(services["principal"], occ.id)  # 3/11 > end -> stop
    with services["database"].create() as uow:
        assert uow.tasks.find_open_by_recurrence_rule(dto.recurrence.rule_id, "maverick") is None


def test_editing_recurrence_preserves_series_and_history(services):
    dto = services["tasks"].create_task(
        services["principal"],
        CreateTaskCommand(title="Monday brief", category="General", due_date=date(2026, 3, 9), recurrence=_weekly(services)),
    )
    series_id = dto.series_id
    rule_id = dto.recurrence.rule_id
    # Edit the recurrence definition in place.
    updated = services["tasks"].update_task(
        services["principal"],
        dto.id,
        UpdateTaskCommand(
            recurrence_provided=True,
            recurrence=RecurrenceInput(
                name="Monday brief (updated)", frequency=Frequency.WEEKLY, day_of_week=0,
                anchor_date=date(2026, 3, 9),
            ),
        ),
    )
    assert updated.series_id == series_id  # identity preserved
    assert updated.recurrence.rule_id == rule_id  # same rule, not a new series
    assert updated.recurrence.name == "Monday brief (updated)"


def test_detach_recurrence_deactivates_rule(services):
    dto = services["tasks"].create_task(
        services["principal"],
        CreateTaskCommand(title="Detach me", category="General", due_date=date(2026, 3, 9), recurrence=_weekly(services)),
    )
    rule_id = dto.recurrence.rule_id
    updated = services["tasks"].update_task(
        services["principal"], dto.id, UpdateTaskCommand(recurrence_provided=True, recurrence=None)
    )
    assert updated.recurrence is None
    with services["database"].create() as uow:
        rule = uow.recurrence_rules.get_by_id(rule_id, "maverick")
    assert rule.active is False  # deactivated, not deleted


def test_no_backfill_fast_forward(services):
    """Completing an overdue recurring task does not create a backlog."""
    dto = services["tasks"].create_task(
        services["principal"],
        CreateTaskCommand(
            title="Overdue daily", category="General", due_date=date(2026, 2, 1),
            recurrence=RecurrenceInput(name="Daily", frequency=Frequency.DAILY, anchor_date=date(2026, 2, 1)),
        ),
    )
    services["tasks"].complete_task(services["principal"], dto.id)
    with services["database"].create() as uow:
        open_now = uow.tasks.list(TaskQuery(status=TaskStatus.OPEN, recurrence_rule_id=dto.recurrence.rule_id), "maverick")
    # Exactly one successor, on/after "today" (2026-03-10), not a February backlog.
    assert len(open_now) == 1
    assert open_now[0].due_date >= date(2026, 3, 10)


def test_successor_failure_rolls_back_completion(services, monkeypatch):
    """If successor creation fails, the completion must not be committed."""
    dto = services["tasks"].create_task(
        services["principal"],
        CreateTaskCommand(title="Monday brief", category="General", due_date=date(2026, 3, 9), recurrence=_weekly(services)),
    )

    def boom(*args, **kwargs):
        raise RuntimeError("simulated successor failure")

    monkeypatch.setattr(services["tasks"], "_generate_successor", boom)
    with pytest.raises(RuntimeError):
        services["tasks"].complete_task(services["principal"], dto.id)

    # The task must still be open — the completion was rolled back.
    with services["database"].create() as uow:
        task = uow.tasks.get_by_id(dto.id, "maverick")
    assert task.status is TaskStatus.OPEN
    assert task.completed_at is None
