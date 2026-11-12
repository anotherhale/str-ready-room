"""Persistence port: repositories, unit of work, and factory.

Application services depend on these protocols.  Concrete adapters (SQLAlchemy
today, others later) implement them.  Repository methods accept and return
domain entities and application-owned criteria only, and never commit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

from ...calendar.entities import CalendarEventRecord
from ...domain.settings.entities import Category, OperatorSettings
from ...domain.tasks.entities import RecurrenceRule, Task
from ...domain.tasks.enums import TaskStatus
from ...mailbox.entities import EmailSource


class PersistenceError(Exception):
    """Application-owned persistence failure.

    Adapters translate driver/ORM exceptions into this type so that application
    services never import SQLAlchemy.
    """

    code = "persistence_error"


@dataclass(frozen=True)
class TaskQuery:
    """Application-owned criteria for listing tasks."""

    status: TaskStatus | None = None
    include_all_statuses: bool = False
    category: str | None = None
    search: str | None = None
    recurrence_rule_id: str | None = None


class TaskRepository(Protocol):
    def get_by_id(self, task_id: str, owner_id: str) -> Task | None: ...

    def list(self, criteria: TaskQuery, owner_id: str) -> list[Task]: ...

    def save(self, task: Task) -> Task: ...

    def delete(self, task_id: str, owner_id: str) -> bool: ...

    def find_open_by_recurrence_rule(self, rule_id: str, owner_id: str) -> Task | None: ...

    def count_by_series(self, series_id: str, owner_id: str) -> int: ...

    def exists_any(self, owner_id: str) -> bool: ...


class RecurrenceRuleRepository(Protocol):
    def get_by_id(self, rule_id: str, owner_id: str) -> RecurrenceRule | None: ...

    def save(self, rule: RecurrenceRule) -> RecurrenceRule: ...

    def list_active(self, owner_id: str) -> list[RecurrenceRule]: ...

    def list_all(self, owner_id: str) -> list[RecurrenceRule]: ...

    def count_tasks_referencing(self, rule_id: str, owner_id: str) -> int: ...

    def delete(self, rule_id: str, owner_id: str) -> bool: ...


class SettingsRepository(Protocol):
    def get(self, owner_id: str) -> OperatorSettings | None: ...

    def save(self, settings: OperatorSettings) -> OperatorSettings: ...


class CategoryRepository(Protocol):
    def list(self, owner_id: str, *, include_inactive: bool = False) -> list[Category]: ...

    def get_by_id(self, category_id: str, owner_id: str) -> Category | None: ...

    def find_by_name(self, name: str, owner_id: str) -> Category | None: ...

    def save(self, category: Category) -> Category: ...

    def delete(self, category_id: str, owner_id: str) -> bool: ...

    def count(self, owner_id: str) -> int: ...


class CalendarEventRepository(Protocol):
    """Cache of provider calendar events, scoped by owner."""

    def get_by_id(self, event_id: str, owner_id: str) -> CalendarEventRecord | None: ...

    def get_by_uid(self, uid: str, calendar_id: str, owner_id: str) -> CalendarEventRecord | None: ...

    def list(
        self, owner_id: str, *, start: date | None = None, end: date | None = None
    ) -> list[CalendarEventRecord]: ...

    def save(self, record: CalendarEventRecord) -> CalendarEventRecord: ...

    def delete(self, event_id: str, owner_id: str) -> bool: ...

    def delete_missing(self, calendar_id: str, keep_uids: set[str], owner_id: str) -> int: ...

    def count(self, owner_id: str) -> int: ...


class EmailSourceRepository(Protocol):
    """Provenance records for captured messages, scoped by owner."""

    def get_by_message_id(self, message_id: str, owner_id: str) -> EmailSource | None: ...

    def list(self, owner_id: str) -> list[EmailSource]: ...

    def save(self, source: EmailSource) -> EmailSource: ...

    def delete(self, source_id: str, owner_id: str) -> bool: ...

    def count(self, owner_id: str) -> int: ...


@runtime_checkable
class DatabasePort(Protocol):
    """A unit of work: exposes repositories and owns the transaction boundary.

    Repositories are read-only properties: a unit of work may not have its
    repository members reassigned.
    """

    @property
    def tasks(self) -> TaskRepository: ...

    @property
    def recurrence_rules(self) -> RecurrenceRuleRepository: ...

    @property
    def settings(self) -> SettingsRepository: ...

    @property
    def categories(self) -> CategoryRepository: ...

    @property
    def calendar_events(self) -> CalendarEventRepository: ...

    @property
    def email_sources(self) -> EmailSourceRepository: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def __enter__(self) -> DatabasePort: ...

    def __exit__(self, exc_type, exc, tb) -> None: ...


class DatabaseFactoryPort(Protocol):
    """Creates units of work and initialises schema."""

    def create(self) -> DatabasePort: ...

    def init_schema(self) -> None: ...


@dataclass(frozen=True)
class ResetSummary:
    """Reported by a reset operation."""

    tasks_deleted: int
    rules_deleted: int
    categories_restored: int
