"""SQLAlchemy ORM models.

This module and its siblings are the only place SQLAlchemy is imported.  Column
types are portable (``String``/``Text``/``Date``/``DateTime``/``Boolean``/
``Integer``) so the same schema runs on SQLite and PostgreSQL.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recurrence_rule_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("recurrence_rules.id"), nullable=True
    )
    series_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    occurrence_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_tasks_owner_status", "owner_id", "status"),
        Index("ix_tasks_owner_due", "owner_id", "due_date"),
    )


class RecurrenceRuleRow(Base):
    __tablename__ = "recurrence_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    interval: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anchor_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_occurrence: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_type: Mapped[str] = mapped_column(String(16), nullable=False, default="never")
    end_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    occurrences_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SettingsRow(Base):
    __tablename__ = "operator_settings"

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    warning_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    seed_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    calendar_seed_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    email_seed_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CategoryRow(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (Index("ix_categories_owner_name", "owner_id", "name"),)


class CalendarEventRow(Base):
    """Cache of provider calendar events.

    ``task_id`` links a cached event to the responsibility it was captured into.
    It was added after the first schema (see DECISIONS D-030/D-031), so the
    additive migration in ``migrations.py`` also creates it on existing volumes.
    """

    __tablename__ = "calendar_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    uid: Mapped[str] = mapped_column(String(255), nullable=False)
    calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    href: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_calendar_owner_uid", "owner_id", "uid", "calendar_id", unique=True),
        Index("ix_calendar_owner_start", "owner_id", "start"),
    )


class EmailSourceRow(Base):
    """Provenance record for a message captured into a task.

    ``message_id`` is unique per owner so recapture updates one row rather than
    inserting a second (see DECISIONS D-026).
    """

    __tablename__ = "email_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String(998), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sender: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (Index("ix_email_source_owner_message", "owner_id", "message_id", unique=True),)
