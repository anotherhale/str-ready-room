"""Recurrence arithmetic tests: frequencies, month-end, leap year, end
conditions, bounded no-backfill, and preview."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.domain.shared.errors import ValidationError
from app.domain.tasks.entities import RecurrenceRule
from app.domain.tasks.enums import EndType, Frequency
from app.domain.tasks.recurrence import (
    add_months,
    first_occurrence,
    nth_occurrence,
    plan_next,
    preview,
)

CREATED = datetime(2026, 1, 1, 12, 0, 0)


def make_rule(**overrides) -> RecurrenceRule:
    base = {
        "id": "rule-1",
        "owner_id": "op-1",
        "name": "Test rule",
        "frequency": Frequency.DAILY,
        "interval": 1,
        "anchor_date": date(2026, 1, 1),
        "created_at": CREATED,
    }
    base.update(overrides)
    return RecurrenceRule(**base)


# -- pure date helpers ----------------------------------------------------
def test_add_months_clamps_to_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 1, 31), 2) == date(2026, 3, 31)
    assert add_months(date(2026, 3, 31), 1) == date(2026, 4, 30)


def test_add_months_leap_year():
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2024, 2, 29), 12) == date(2025, 2, 28)


# -- frequency arithmetic -------------------------------------------------
def test_daily_sequence():
    rule = make_rule(frequency=Frequency.DAILY, interval=2)
    assert nth_occurrence(rule, 1) == date(2026, 1, 1)
    assert nth_occurrence(rule, 3) == date(2026, 1, 5)


def test_weekly_with_weekday_snaps_forward():
    # 2026-01-01 is a Thursday; day_of_week=0 (Monday) -> 2026-01-05
    rule = make_rule(frequency=Frequency.WEEKLY, interval=1, day_of_week=0, anchor_date=date(2026, 1, 1))
    assert first_occurrence(rule) == date(2026, 1, 5)
    assert nth_occurrence(rule, 2) == date(2026, 1, 12)


def test_monthly_month_end_determinism():
    rule = make_rule(frequency=Frequency.MONTHLY, interval=1, anchor_date=date(2026, 1, 31))
    assert nth_occurrence(rule, 1) == date(2026, 1, 31)
    assert nth_occurrence(rule, 2) == date(2026, 2, 28)
    assert nth_occurrence(rule, 3) == date(2026, 3, 31)  # not 28 March


def test_quarterly_sequence():
    rule = make_rule(frequency=Frequency.QUARTERLY, interval=1, anchor_date=date(2026, 1, 15))
    assert nth_occurrence(rule, 1) == date(2026, 1, 15)
    assert nth_occurrence(rule, 2) == date(2026, 4, 15)
    assert nth_occurrence(rule, 3) == date(2026, 7, 15)


def test_yearly_leap_day_clamps():
    rule = make_rule(frequency=Frequency.YEARLY, interval=1, anchor_date=date(2024, 2, 29))
    assert nth_occurrence(rule, 1) == date(2024, 2, 29)
    assert nth_occurrence(rule, 2) == date(2025, 2, 28)
    assert nth_occurrence(rule, 4) == date(2027, 2, 28)
    assert nth_occurrence(rule, 5) == date(2028, 2, 29)  # leap year restores Feb 29


def test_interval_must_be_positive():
    with pytest.raises(ValidationError):
        make_rule(interval=0)


# -- plan_next ------------------------------------------------------------
def test_plan_next_is_strictly_after():
    rule = make_rule(frequency=Frequency.DAILY, interval=1)
    plan = plan_next(rule, date(2026, 1, 1))
    assert plan.date == date(2026, 1, 2)
    assert plan.skipped == 0


def test_plan_next_no_backfill_counts_skipped():
    rule = make_rule(frequency=Frequency.DAILY, interval=1, anchor_date=date(2026, 1, 1))
    # Complete the first occurrence, then "today" has moved to the 10th.
    rule.occurrences_generated = 1
    plan = plan_next(rule, date(2026, 1, 1), today=date(2026, 1, 10))
    assert plan.date == date(2026, 1, 10)
    assert plan.skipped == 8  # 2nd..9th skipped, 10th generated


def test_plan_next_bounded_fast_forward():
    rule = make_rule(frequency=Frequency.DAILY, interval=1, anchor_date=date(2000, 1, 1))
    plan = plan_next(rule, date(2000, 1, 1), today=date(2100, 1, 1), max_fast_forward=5)
    assert plan.date is None
    assert plan.bounded is True
    assert plan.skipped == 5


def test_plan_next_end_count():
    rule = make_rule(frequency=Frequency.DAILY, end_type=EndType.COUNT, end_count=3)
    rule.occurrences_generated = 3
    plan = plan_next(rule, date(2026, 1, 3))
    assert plan.date is None
    assert plan.exhausted is True


def test_plan_next_end_date():
    rule = make_rule(frequency=Frequency.DAILY, end_type=EndType.ON_DATE, end_date=date(2026, 1, 3))
    plan = plan_next(rule, date(2026, 1, 3))
    assert plan.date is None
    assert plan.exhausted is True
    plan_ok = plan_next(rule, date(2026, 1, 2))
    assert plan_ok.date == date(2026, 1, 3)


def test_plan_next_inactive_rule_exhausted():
    rule = make_rule(active=False)
    assert plan_next(rule, date(2026, 1, 1)).exhausted is True


# -- preview --------------------------------------------------------------
def test_preview_returns_requested_count():
    rule = make_rule(frequency=Frequency.WEEKLY, day_of_week=0, anchor_date=date(2026, 1, 1))
    dates = preview(rule, count=3)
    assert dates == [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19)]


def test_preview_respects_end_count():
    rule = make_rule(frequency=Frequency.DAILY, end_type=EndType.COUNT, end_count=2)
    assert preview(rule, count=5) == [date(2026, 1, 1), date(2026, 1, 2)]


def test_preview_after_date():
    rule = make_rule(frequency=Frequency.DAILY)
    assert preview(rule, count=2, after_date=date(2026, 1, 10)) == [date(2026, 1, 11), date(2026, 1, 12)]
