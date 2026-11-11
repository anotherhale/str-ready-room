"""Task aggregate and RecurrenceRule entity.

Plain Python dataclasses with lifecycle methods that enforce domain
invariants.  Nothing here imports a framework, ORM, or transport schema.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from ..shared.errors import ConflictError, ValidationError
from .enums import EndType, Frequency, Priority, TaskStatus
from .events import (
    DomainEvent,
    TaskCompleted,
    TaskCreated,
    TaskDeleted,
    TaskReopened,
)
from .value_objects import normalize_description, normalize_title


@dataclass
class Task:
    """A single responsibility owned by one operator."""

    id: str
    owner_id: str
    title: str
    category: str
    created_at: datetime
    updated_at: datetime
    status: TaskStatus = TaskStatus.OPEN
    priority: Priority = Priority.NORMAL
    description: str | None = None
    due_date: date | None = None
    completed_at: datetime | None = None
    recurrence_rule_id: str | None = None
    series_id: str | None = None
    occurrence_number: int = 1
    _events: list[DomainEvent] = field(default_factory=list, repr=False, compare=False)

    # -- lifecycle -----------------------------------------------------
    def complete(self, now: datetime) -> bool:
        """Complete the task.  Idempotent: a second call is a no-op.

        Returns ``True`` when this call performed the transition.
        """
        if self.status is TaskStatus.COMPLETED:
            return False
        self.status = TaskStatus.COMPLETED
        self.completed_at = now
        self.updated_at = now
        self._events.append(TaskCompleted(task_id=self.id))
        return True

    def reopen(self, now: datetime) -> bool:
        """Return the task to the active set.  Idempotent."""
        if self.status is TaskStatus.OPEN and self.completed_at is None:
            return False
        self.status = TaskStatus.OPEN
        self.completed_at = None
        self.updated_at = now
        self._events.append(TaskReopened(task_id=self.id))
        return True

    def update(
        self,
        now: datetime,
        *,
        title: str | None = None,
        description: str | None = None,
        description_provided: bool = False,
        category: str | None = None,
        priority: Priority | None = None,
        due_date: date | None = None,
        due_date_provided: bool = False,
    ) -> None:
        """Apply an edit.  ``*_provided`` distinguishes "clear" from "leave"."""
        if title is not None:
            self.title = normalize_title(title)
        if description_provided:
            self.description = normalize_description(description)
        if category is not None:
            self.category = category
        if priority is not None:
            self.priority = priority
        if due_date_provided:
            self.due_date = due_date
        self.updated_at = now

    def mark_deleted(self) -> None:
        self._events.append(TaskDeleted(task_id=self.id))

    def attach_to_series(self, series_id: str, rule_id: str, occurrence_number: int) -> None:
        self.series_id = series_id
        self.recurrence_rule_id = rule_id
        self.occurrence_number = occurrence_number

    def record_event(self, event: DomainEvent) -> None:
        self._events.append(event)

    def drain_events(self) -> list[DomainEvent]:
        drained, self._events = self._events, []
        return drained

    @property
    def is_open(self) -> bool:
        return self.status is TaskStatus.OPEN

    @property
    def is_completed(self) -> bool:
        return self.status is TaskStatus.COMPLETED

    @property
    def is_recurring(self) -> bool:
        return self.recurrence_rule_id is not None

    def __post_init__(self) -> None:
        self.title = normalize_title(self.title)
        if self.occurrence_number < 1:
            raise ValidationError("occurrence_number must be >= 1")

    @classmethod
    def create(
        cls,
        *,
        id: str,
        owner_id: str,
        title: str,
        category: str,
        now: datetime,
        priority: Priority = Priority.NORMAL,
        description: str | None = None,
        due_date: date | None = None,
        series_id: str | None = None,
        recurrence_rule_id: str | None = None,
        occurrence_number: int = 1,
    ) -> Task:
        task = cls(
            id=id,
            owner_id=owner_id,
            title=title,
            category=category,
            priority=priority,
            description=description,
            due_date=due_date,
            created_at=now,
            updated_at=now,
            series_id=series_id,
            recurrence_rule_id=recurrence_rule_id,
            occurrence_number=occurrence_number,
        )
        task._events.append(TaskCreated(task_id=id))
        return task


@dataclass
class RecurrenceRule:
    """A recurrence definition.  Occurrences are ordinary Task rows."""

    id: str
    owner_id: str
    name: str
    frequency: Frequency
    interval: int
    anchor_date: date
    created_at: datetime
    day_of_week: int | None = None
    next_occurrence: date | None = None
    end_type: EndType = EndType.NEVER
    end_count: int | None = None
    end_date: date | None = None
    occurrences_generated: int = 0
    active: bool = True

    def __post_init__(self) -> None:
        if self.interval < 1:
            raise ValidationError("Recurrence interval must be at least 1")
        if self.day_of_week is not None and not (0 <= self.day_of_week <= 6):
            raise ValidationError("day_of_week must be between 0 (Monday) and 6 (Sunday)")
        if self.end_type is EndType.COUNT and (self.end_count is None or self.end_count < 1):
            raise ValidationError("end_count must be >= 1 when end_type is 'count'")
        if self.end_type is EndType.ON_DATE and self.end_date is None:
            raise ValidationError("end_date is required when end_type is 'on_date'")
        if self.occurrences_generated < 0:
            raise ValidationError("occurrences_generated must not be negative")

    def record_generation(self) -> None:
        self.occurrences_generated += 1

    def deactivate(self) -> None:
        if not self.active:
            raise ConflictError("Recurrence rule is already inactive")
        self.active = False
