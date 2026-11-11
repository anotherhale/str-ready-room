"""Command and query objects for application use cases.

Explicit commands/queries keep service signatures stable and make it obvious
which inputs are optional vs. "clear this field".
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...domain.tasks.enums import EndType, Frequency, Priority


@dataclass(frozen=True)
class RecurrenceInput:
    """Recurrence configuration supplied when creating/editing a task."""

    name: str
    frequency: Frequency
    interval: int = 1
    day_of_week: int | None = None
    anchor_date: date | None = None
    end_type: EndType = EndType.NEVER
    end_count: int | None = None
    end_date: date | None = None
    active: bool = True


@dataclass(frozen=True)
class CreateTaskCommand:
    title: str
    category: str
    priority: Priority = Priority.NORMAL
    description: str | None = None
    due_date: date | None = None
    recurrence: RecurrenceInput | None = None


@dataclass(frozen=True)
class UpdateTaskCommand:
    title: str | None = None
    description: str | None = None
    description_provided: bool = False
    category: str | None = None
    priority: Priority | None = None
    due_date: date | None = None
    due_date_provided: bool = False
    # ``recurrence_provided`` distinguishes "leave recurrence alone" from
    # "detach recurrence" (None) and "set/update recurrence".
    recurrence_provided: bool = False
    recurrence: RecurrenceInput | None = None


@dataclass(frozen=True)
class ListTasksQuery:
    status: str | None = None  # 'open' | 'completed' | 'all' | None
    category: str | None = None
    search: str | None = None
    sort: str = "due_date"


@dataclass(frozen=True)
class UpdateSettingsCommand:
    warning_window_days: int | None = None
    timezone: str | None = None


@dataclass(frozen=True)
class CreateCategoryCommand:
    name: str


@dataclass(frozen=True)
class UpdateCategoryCommand:
    name: str | None = None
    active: bool | None = None
