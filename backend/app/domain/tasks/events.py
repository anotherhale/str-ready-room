"""Domain events emitted by the task aggregate.

Events are plain data.  They are recorded on the aggregate and drained by the
application service; nothing in the domain publishes or persists them.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainEvent:
    """Base marker for domain events."""


@dataclass(frozen=True)
class TaskCreated(DomainEvent):
    task_id: str


@dataclass(frozen=True)
class TaskCompleted(DomainEvent):
    task_id: str


@dataclass(frozen=True)
class TaskReopened(DomainEvent):
    task_id: str


@dataclass(frozen=True)
class TaskDeleted(DomainEvent):
    task_id: str


@dataclass(frozen=True)
class SuccessorTaskCreated(DomainEvent):
    task_id: str
    series_id: str
    occurrence_number: int
