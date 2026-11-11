"""Task-related enumerations."""
from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    OPEN = "open"
    COMPLETED = "completed"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Urgency(str, Enum):
    """Derived urgency.  Never persisted as an editable task field."""

    OVERDUE = "overdue"
    DUE = "due"
    WATCH = "watch"
    UP_NEXT = "up_next"
    NORMAL = "normal"
    COMPLETED = "completed"


class Frequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class EndType(str, Enum):
    NEVER = "never"
    COUNT = "count"
    ON_DATE = "on_date"
