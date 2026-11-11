"""Boundary tests for urgency derivation."""
from __future__ import annotations

from datetime import date

import pytest

from app.domain.tasks.enums import Urgency
from app.domain.tasks.urgency import (
    DEFAULT_WARNING_WINDOW,
    MAX_WARNING_WINDOW,
    MIN_WARNING_WINDOW,
    compute_urgency,
    days_until_due,
    validate_warning_window,
)

TODAY = date(2026, 3, 10)


def test_completed_status_wins_over_due_date():
    assert (
        compute_urgency(status="completed", due_date=date(2020, 1, 1), today=TODAY, warning_window_days=3)
        is Urgency.COMPLETED
    )


def test_no_due_date_is_normal():
    assert compute_urgency(status="open", due_date=None, today=TODAY, warning_window_days=3) is Urgency.NORMAL


@pytest.mark.parametrize(
    ("due", "expected"),
    [
        (date(2026, 3, 9), Urgency.OVERDUE),   # yesterday
        (date(2026, 3, 10), Urgency.DUE),      # today (boundary)
        (date(2026, 3, 11), Urgency.WATCH),    # today + 1
        (date(2026, 3, 13), Urgency.WATCH),    # today + window (inclusive boundary)
        (date(2026, 3, 14), Urgency.UP_NEXT),  # today + window + 1
    ],
)
def test_urgency_boundaries(due, expected):
    assert compute_urgency(status="open", due_date=due, today=TODAY, warning_window_days=3) is expected


def test_watch_window_is_configurable():
    assert compute_urgency(status="open", due_date=date(2026, 3, 12), today=TODAY, warning_window_days=1) is Urgency.UP_NEXT
    assert compute_urgency(status="open", due_date=date(2026, 3, 12), today=TODAY, warning_window_days=2) is Urgency.WATCH


def test_days_until_due():
    assert days_until_due(None, TODAY) is None
    assert days_until_due(date(2026, 3, 13), TODAY) == 3
    assert days_until_due(date(2026, 3, 8), TODAY) == -2


@pytest.mark.parametrize("value", [MIN_WARNING_WINDOW, DEFAULT_WARNING_WINDOW, MAX_WARNING_WINDOW])
def test_validate_warning_window_accepts_bounds(value):
    assert validate_warning_window(value) == value


@pytest.mark.parametrize("value", [0, -1, MAX_WARNING_WINDOW + 1, 1000])
def test_validate_warning_window_rejects_out_of_range(value):
    with pytest.raises(ValueError):
        validate_warning_window(value)


@pytest.mark.parametrize("value", [True, "3", 2.5, None])
def test_validate_warning_window_rejects_non_integer(value):
    with pytest.raises(ValueError):
        validate_warning_window(value)  # type: ignore[arg-type]
