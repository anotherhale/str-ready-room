"""Pydantic v2 request schemas (transport layer).

These validate request *shape*.  Business rules remain in the domain and
application layers.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from ...domain.tasks.enums import EndType, Frequency, Priority


class RecurrenceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    frequency: Frequency
    interval: int = Field(default=1, ge=1, le=365)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    anchor_date: date | None = None
    end_type: EndType = EndType.NEVER
    end_count: int | None = Field(default=None, ge=1, le=1000)
    end_date: date | None = None
    active: bool = True


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    category: str = Field(min_length=1, max_length=80)
    priority: Priority = Priority.NORMAL
    description: str | None = Field(default=None, max_length=5000)
    due_date: date | None = None
    recurrence: RecurrenceRequest | None = None


class TaskUpdateRequest(BaseModel):
    """Partial update.

    ``description``/``due_date``/``recurrence`` use ``*_set`` flags so the client
    can distinguish "leave unchanged" from "clear".
    """

    title: str | None = Field(default=None, min_length=1, max_length=300)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    priority: Priority | None = None
    description: str | None = Field(default=None, max_length=5000)
    description_set: bool = False
    due_date: date | None = None
    due_date_set: bool = False
    recurrence: RecurrenceRequest | None = None
    recurrence_set: bool = False


class SettingsUpdateRequest(BaseModel):
    warning_window_days: int | None = Field(default=None, ge=1, le=60)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    active: bool | None = None


class RecurrencePreviewRequest(BaseModel):
    name: str = Field(default="Preview", min_length=1, max_length=200)
    frequency: Frequency
    interval: int = Field(default=1, ge=1, le=365)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    anchor_date: date | None = None
    end_type: EndType = EndType.NEVER
    end_count: int | None = Field(default=None, ge=1, le=1000)
    end_date: date | None = None
    active: bool = True
    count: int = Field(default=5, ge=1, le=50)


# -- calendar -------------------------------------------------------------
class CalendarEventCreateRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=300)
    start: datetime
    end: datetime | None = None
    all_day: bool = False
    location: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    calendar_id: str | None = Field(default=None, max_length=200)


class CalendarCaptureRequest(BaseModel):
    """Turn a cached event into a responsibility.  All fields are optional."""

    category: str | None = Field(default=None, min_length=1, max_length=80)
    priority: Priority | None = None
    due_date: date | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=4000)


# -- email ----------------------------------------------------------------
class EmailCaptureRequest(BaseModel):
    """Turn a mailbox message into a responsibility.  All fields are optional."""

    category: str | None = Field(default=None, min_length=1, max_length=80)
    priority: Priority | None = None
    due_date: date | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
