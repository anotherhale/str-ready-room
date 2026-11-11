"""Mappers between domain entities and ORM rows.

Mapping lives here so the domain never sees a row and the repositories stay
thin.  Enum columns are stored as their string values and rebuilt on load.
"""
from __future__ import annotations

from ....domain.settings.entities import Category, OperatorSettings
from ....domain.tasks.entities import RecurrenceRule, Task
from ....domain.tasks.enums import EndType, Frequency, Priority, TaskStatus
from .models import CategoryRow, RecurrenceRuleRow, SettingsRow, TaskRow


# -- Task -----------------------------------------------------------------
def task_to_row(task: Task) -> TaskRow:
    return TaskRow(
        id=task.id,
        owner_id=task.owner_id,
        title=task.title,
        description=task.description,
        category=task.category,
        status=task.status.value,
        priority=task.priority.value,
        due_date=task.due_date,
        created_at=task.created_at,
        updated_at=task.updated_at,
        completed_at=task.completed_at,
        recurrence_rule_id=task.recurrence_rule_id,
        series_id=task.series_id,
        occurrence_number=task.occurrence_number,
    )


def apply_task_to_row(task: Task, row: TaskRow) -> None:
    row.title = task.title
    row.description = task.description
    row.category = task.category
    row.status = task.status.value
    row.priority = task.priority.value
    row.due_date = task.due_date
    row.updated_at = task.updated_at
    row.completed_at = task.completed_at
    row.recurrence_rule_id = task.recurrence_rule_id
    row.series_id = task.series_id
    row.occurrence_number = task.occurrence_number


def row_to_task(row: TaskRow) -> Task:
    return Task(
        id=row.id,
        owner_id=row.owner_id,
        title=row.title,
        description=row.description,
        category=row.category,
        status=TaskStatus(row.status),
        priority=Priority(row.priority),
        due_date=row.due_date,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
        recurrence_rule_id=row.recurrence_rule_id,
        series_id=row.series_id,
        occurrence_number=row.occurrence_number,
    )


# -- RecurrenceRule -------------------------------------------------------
def rule_to_row(rule: RecurrenceRule) -> RecurrenceRuleRow:
    return RecurrenceRuleRow(
        id=rule.id,
        owner_id=rule.owner_id,
        name=rule.name,
        frequency=rule.frequency.value,
        interval=rule.interval,
        day_of_week=rule.day_of_week,
        anchor_date=rule.anchor_date,
        next_occurrence=rule.next_occurrence,
        end_type=rule.end_type.value,
        end_count=rule.end_count,
        end_date=rule.end_date,
        occurrences_generated=rule.occurrences_generated,
        active=rule.active,
        created_at=rule.created_at,
    )


def apply_rule_to_row(rule: RecurrenceRule, row: RecurrenceRuleRow) -> None:
    row.name = rule.name
    row.frequency = rule.frequency.value
    row.interval = rule.interval
    row.day_of_week = rule.day_of_week
    row.anchor_date = rule.anchor_date
    row.next_occurrence = rule.next_occurrence
    row.end_type = rule.end_type.value
    row.end_count = rule.end_count
    row.end_date = rule.end_date
    row.occurrences_generated = rule.occurrences_generated
    row.active = rule.active


def row_to_rule(row: RecurrenceRuleRow) -> RecurrenceRule:
    return RecurrenceRule(
        id=row.id,
        owner_id=row.owner_id,
        name=row.name,
        frequency=Frequency(row.frequency),
        interval=row.interval,
        day_of_week=row.day_of_week,
        anchor_date=row.anchor_date,
        next_occurrence=row.next_occurrence,
        end_type=EndType(row.end_type),
        end_count=row.end_count,
        end_date=row.end_date,
        occurrences_generated=row.occurrences_generated,
        active=row.active,
        created_at=row.created_at,
    )


# -- Settings -------------------------------------------------------------
def row_to_settings(row: SettingsRow) -> OperatorSettings:
    return OperatorSettings(
        owner_id=row.owner_id,
        warning_window_days=row.warning_window_days,
        timezone=row.timezone,
        seed_version=row.seed_version,
        updated_at=row.updated_at,
    )


def settings_to_row(settings: OperatorSettings) -> SettingsRow:
    return SettingsRow(
        owner_id=settings.owner_id,
        warning_window_days=settings.warning_window_days,
        timezone=settings.timezone,
        seed_version=settings.seed_version,
        updated_at=settings.updated_at,
    )


# -- Category -------------------------------------------------------------
def row_to_category(row: CategoryRow) -> Category:
    return Category(
        id=row.id,
        owner_id=row.owner_id,
        name=row.name,
        created_at=row.created_at,
        active=row.active,
        is_default=row.is_default,
    )


def category_to_row(category: Category) -> CategoryRow:
    return CategoryRow(
        id=category.id,
        owner_id=category.owner_id,
        name=category.name,
        created_at=category.created_at,
        active=category.active,
        is_default=category.is_default,
    )
