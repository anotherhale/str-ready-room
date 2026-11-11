"""Small immutable value objects for the task aggregate."""
from __future__ import annotations

from dataclasses import dataclass

from ..shared.errors import ValidationError

PRIORITY_ORDER = {"low": 0, "normal": 1, "high": 2, "critical": 3}


@dataclass(frozen=True)
class TaskId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationError("TaskId value is required")

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclass(frozen=True)
class SeriesId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationError("SeriesId value is required")

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclass(frozen=True)
class RecurrenceRuleId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationError("RecurrenceRuleId value is required")

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


def normalize_title(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValidationError("Task title is required")
    if len(cleaned) > 300:
        raise ValidationError("Task title must be 300 characters or fewer")
    return cleaned


def normalize_description(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def normalize_category(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValidationError("Category is required")
    if len(cleaned) > 80:
        raise ValidationError("Category must be 80 characters or fewer")
    return cleaned


def category_key(value: str) -> str:
    """Case-insensitive identity used for duplicate detection."""
    return normalize_category(value).casefold()


def priority_rank(priority: str) -> int:
    return PRIORITY_ORDER.get(priority, 1)
