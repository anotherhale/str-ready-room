"""Pure urgency derivation.

Urgency is computed on read from the task's due date, status, and the
operator's local ``today``.  It is never persisted and never editable.

This module is the single authoritative implementation of the rule; the
frontend only maps the resulting states to labels, icons, and styles.
"""
from __future__ import annotations

from datetime import date

from ..shared.errors import ValidationError
from .enums import Urgency

#: Sensible bounds for the configurable warning window (in days).
MIN_WARNING_WINDOW = 1
MAX_WARNING_WINDOW = 60
DEFAULT_WARNING_WINDOW = 3


def validate_warning_window(days: int) -> int:
    if not isinstance(days, int) or isinstance(days, bool):
        raise ValidationError("Warning window must be an integer number of days")
    if days < MIN_WARNING_WINDOW or days > MAX_WARNING_WINDOW:
        raise ValidationError(
            f"Warning window must be between {MIN_WARNING_WINDOW} and {MAX_WARNING_WINDOW} days"
        )
    return days


def compute_urgency(
    *,
    status: str,
    due_date: date | None,
    today: date,
    warning_window_days: int,
) -> Urgency:
    """Derive urgency for a task.

    Boundaries (all inclusive where noted):

    * completed status -> COMPLETED
    * no due date       -> NORMAL
    * due_date <  today -> OVERDUE
    * due_date == today -> DUE
    * due_date <= today + warning_window_days -> WATCH
    * otherwise         -> UP_NEXT
    """
    if status == "completed":
        return Urgency.COMPLETED
    if due_date is None:
        return Urgency.NORMAL
    delta = (due_date - today).days
    if delta < 0:
        return Urgency.OVERDUE
    if delta == 0:
        return Urgency.DUE
    if delta <= warning_window_days:
        return Urgency.WATCH
    return Urgency.UP_NEXT


def days_until_due(due_date: date | None, today: date) -> int | None:
    if due_date is None:
        return None
    return (due_date - today).days


#: The set of urgencies that belong in active operational sections.
ACTIVE_URGENCIES = frozenset(
    {Urgency.OVERDUE, Urgency.DUE, Urgency.WATCH, Urgency.UP_NEXT, Urgency.NORMAL}
)
