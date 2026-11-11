"""Application DTOs.

Plain dataclasses returned by application services.  Inbound adapters map these
to Pydantic response schemas; the application layer never imports Pydantic
transport schemas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from ...domain.tasks.enums import EndType, Frequency, Priority, TaskStatus, Urgency


@dataclass(frozen=True)
class RecurrenceSummary:
    rule_id: str
    name: str
    frequency: Frequency
    interval: int
    day_of_week: int | None
    end_type: EndType
    active: bool
    occurrences_generated: int
    next_occurrence: date | None


@dataclass(frozen=True)
class TaskDTO:
    id: str
    owner_id: str
    title: str
    description: str | None
    category: str
    status: TaskStatus
    priority: Priority
    due_date: date | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    series_id: str | None
    occurrence_number: int
    recurrence: RecurrenceSummary | None
    # derived (computed on read, never stored)
    urgency: Urgency
    days_until_due: int | None


@dataclass(frozen=True)
class CategoryDTO:
    id: str
    name: str
    active: bool
    is_default: bool


@dataclass(frozen=True)
class SettingsDTO:
    warning_window_days: int
    timezone: str
    categories: list[CategoryDTO] = field(default_factory=list)


@dataclass(frozen=True)
class CountsDTO:
    overdue: int
    due: int
    watch: int
    horizon: int
    completed_this_week: int


@dataclass(frozen=True)
class DashboardDTO:
    today: date
    timezone: str
    greeting_name: str
    warning_window_days: int
    watch_label: str
    readiness_summary: str
    counts: CountsDTO
    today_tasks: list[TaskDTO]
    watch_tasks: list[TaskDTO]
    horizon_tasks: list[TaskDTO]


@dataclass(frozen=True)
class BriefingDTO:
    date: date
    timezone: str
    today: list[TaskDTO]
    upcoming: list[TaskDTO]
    overdue: list[TaskDTO]
    recurring_obligations: list[TaskDTO]
    look_ahead: str


@dataclass(frozen=True)
class RecurrenceOverviewDTO:
    rules: list[RecurrenceSummary]
    upcoming: list[tuple[str, date]]  # (rule name, next date)


@dataclass(frozen=True)
class RecurrencePreviewDTO:
    dates: list[date]


@dataclass(frozen=True)
class ResetResultDTO:
    tasks_deleted: int
    rules_deleted: int
    categories_restored: int
