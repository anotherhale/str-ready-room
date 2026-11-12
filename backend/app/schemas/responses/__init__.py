"""Pydantic v2 response schemas (transport layer).

Includes computed fields (``urgency``, ``days_until_due``, embedded recurrence)
which are derived, never stored.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from ...domain.tasks.enums import EndType, Frequency, Priority, TaskStatus, Urgency


class RecurrenceSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_id: str
    name: str
    frequency: Frequency
    interval: int
    day_of_week: int | None
    end_type: EndType
    active: bool
    occurrences_generated: int
    next_occurrence: date | None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    recurrence: RecurrenceSummaryResponse | None
    urgency: Urgency
    days_until_due: int | None


class TaskListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[TaskResponse]
    total: int


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    active: bool
    is_default: bool


class SettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    warning_window_days: int
    timezone: str
    categories: list[CategoryResponse]


class TimezonesResponse(BaseModel):
    """Curated IANA shortlist for the Settings selector.

    ``default_timezone`` is the operator's configured zone so the UI can
    guarantee it is selectable even if it is not in the shortlist.
    """

    timezones: list[str]
    default_timezone: str


class CountsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    overdue: int
    due: int
    watch: int
    horizon: int
    completed_this_week: int


class DashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    today: date
    timezone: str
    greeting_name: str
    warning_window_days: int
    watch_label: str
    readiness_summary: str
    counts: CountsResponse
    today_tasks: list[TaskResponse]
    watch_tasks: list[TaskResponse]
    horizon_tasks: list[TaskResponse]


class BriefingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    timezone: str
    today: list[TaskResponse]
    upcoming: list[TaskResponse]
    overdue: list[TaskResponse]
    recurring_obligations: list[TaskResponse]
    look_ahead: str


class RecurrencePreviewResponse(BaseModel):
    dates: list[date]


class RecurrenceOverviewItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_id: str
    name: str
    frequency: Frequency
    interval: int
    day_of_week: int | None
    end_type: EndType
    active: bool
    occurrences_generated: int
    next_occurrence: date | None


class RecurrenceOverviewResponse(BaseModel):
    rules: list[RecurrenceOverviewItem]
    upcoming: list[UpcomingOccurrenceResponse]


class UpcomingOccurrenceResponse(BaseModel):
    name: str
    date: date


class ResetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tasks_deleted: int
    rules_deleted: int
    categories_restored: int


class DemoArrivalResponse(BaseModel):
    """Result of a live demo arrival injection (one email, one calendar event)."""

    model_config = ConfigDict(from_attributes=True)

    email_delivered: bool
    email_detail: str
    calendar_delivered: bool
    calendar_detail: str


class HealthResponse(BaseModel):
    status: str
    environment: str
    database_adapter: str
    auth_provider: str


class PrincipalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    timezone: str
    roles: list[str]


# -- calendar -------------------------------------------------------------
class CalendarEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    uid: str
    calendar_id: str
    summary: str
    start: datetime
    end: datetime | None
    all_day: bool
    location: str | None
    description: str | None
    task_id: str | None
    captured: bool


class CalendarAgendaResponse(BaseModel):
    date: date
    timezone: str
    window_days: int
    available: bool
    events: list[CalendarEventResponse]
    detail: str | None = None


class CalendarStatusResponse(BaseModel):
    available: bool
    provider: str | None
    calendar_id: str | None
    cached_events: int
    last_synced_at: datetime | None
    detail: str | None = None


class CalendarSyncResponse(BaseModel):
    fetched: int
    created: int
    updated: int
    pruned: int
    synced_at: datetime


# -- email ----------------------------------------------------------------
class EmailSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: str
    sender: str
    subject: str
    received_at: datetime | None
    snippet: str
    captured: bool
    task_id: str | None


class EmailMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: str
    sender: str
    subject: str
    received_at: datetime | None
    body: str
    captured: bool
    task_id: str | None


class MailboxStatusResponse(BaseModel):
    available: bool
    provider: str | None
    mailbox: str | None
    message_count: int
    captured_count: int
    detail: str | None = None


RecurrenceOverviewResponse.model_rebuild()
