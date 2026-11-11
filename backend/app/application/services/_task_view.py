"""Shared TaskDTO builder.

Kept in one place so the task, dashboard, and briefing services all derive
urgency and embed recurrence identically.  The backend is the single
authoritative source of these derived values.
"""
from __future__ import annotations

from datetime import date

from ...domain.tasks.entities import Task
from ...domain.tasks.urgency import compute_urgency, days_until_due
from ..dto import RecurrenceSummary, TaskDTO


def to_task_dto(uow, task: Task, *, owner_id: str, today: date, warning_window: int) -> TaskDTO:  # noqa: ANN001
    recurrence = None
    if task.recurrence_rule_id is not None:
        rule = uow.recurrence_rules.get_by_id(task.recurrence_rule_id, owner_id)
        if rule is not None:
            recurrence = RecurrenceSummary(
                rule_id=rule.id,
                name=rule.name,
                frequency=rule.frequency,
                interval=rule.interval,
                day_of_week=rule.day_of_week,
                end_type=rule.end_type,
                active=rule.active,
                occurrences_generated=rule.occurrences_generated,
                next_occurrence=rule.next_occurrence,
            )
    return TaskDTO(
        id=task.id,
        owner_id=task.owner_id,
        title=task.title,
        description=task.description,
        category=task.category,
        status=task.status,
        priority=task.priority,
        due_date=task.due_date,
        created_at=task.created_at,
        updated_at=task.updated_at,
        completed_at=task.completed_at,
        series_id=task.series_id,
        occurrence_number=task.occurrence_number,
        recurrence=recurrence,
        urgency=compute_urgency(
            status=task.status.value,
            due_date=task.due_date,
            today=today,
            warning_window_days=warning_window,
        ),
        days_until_due=days_until_due(task.due_date, today),
    )
