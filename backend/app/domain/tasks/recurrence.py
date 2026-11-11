"""Pure recurrence arithmetic.

Design notes
------------
* A recurring series is a *chain of ordinary Task rows* sharing a ``series_id``.
  There is no separate occurrence table.
* Arithmetic is anchored on a fixed first-occurrence date so that month-end and
  leap-year behaviour is deterministic: a rule anchored on 31 January yields
  31 March after a February clamp (not 28 March).
* No large backlog of missed occurrences is ever backfilled.  ``plan_next``
  fast-forwards over missed dates in a *bounded* loop and reports how many it
  skipped so the caller can keep ``occurrences_generated`` truthful.

This module has no dependency on persistence, the clock, or the UI.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from ..shared.errors import ValidationError
from .entities import RecurrenceRule
from .enums import EndType, Frequency

#: Upper bound on occurrences skipped during fast-forward.  Prevents an
#: unbounded loop if a rule is anchored far in the past.
MAX_FAST_FORWARD = 5000

#: Default number of upcoming dates returned by a preview.
DEFAULT_PREVIEW_COUNT = 5


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def add_months(value: date, months: int) -> date:
    """Add months to a date, clamping the day to the target month's end."""
    total = value.year * 12 + (value.month - 1) + months
    year, month_index = divmod(total, 12)
    month = month_index + 1
    day = min(value.day, days_in_month(year, month))
    return date(year, month, day)


def _period_days(frequency: Frequency, interval: int) -> int:
    if frequency is Frequency.DAILY:
        return interval
    if frequency is Frequency.WEEKLY:
        return interval * 7
    raise ValidationError(f"{frequency} is not a fixed-length period")


def first_occurrence(rule: RecurrenceRule) -> date:
    """The series' first occurrence date.

    For a weekly rule with a weekday the anchor is snapped forward to the first
    matching weekday on or after the anchor date.
    """
    anchor = rule.anchor_date
    if rule.frequency is Frequency.WEEKLY and rule.day_of_week is not None:
        delta = (rule.day_of_week - anchor.weekday()) % 7
        return anchor + timedelta(days=delta)
    return anchor


def nth_occurrence(rule: RecurrenceRule, n: int) -> date:
    """The ``n``-th occurrence (1-based) of the series."""
    if n < 1:
        raise ValidationError("Occurrence index must be >= 1")
    first = first_occurrence(rule)
    step = n - 1
    freq = rule.frequency
    if freq is Frequency.DAILY:
        return first + timedelta(days=step * rule.interval)
    if freq is Frequency.WEEKLY:
        return first + timedelta(days=step * rule.interval * 7)
    if freq is Frequency.MONTHLY:
        return add_months(first, step * rule.interval)
    if freq is Frequency.QUARTERLY:
        return add_months(first, step * rule.interval * 3)
    if freq is Frequency.YEARLY:
        return add_months(first, step * rule.interval * 12)
    raise ValidationError(f"Unsupported frequency: {freq}")


def _occurrence_index_after(rule: RecurrenceRule, after_date: date) -> int:
    """Estimate the index of the first occurrence strictly after ``after_date``.

    Uses arithmetic to jump close to the answer, then adjusts by at most a
    couple of steps, so the result is exact and the work is bounded.
    """
    first = first_occurrence(rule)
    if after_date < first:
        return 1
    freq = rule.frequency
    if freq is Frequency.DAILY:
        approx = (after_date - first).days // rule.interval
    elif freq is Frequency.WEEKLY:
        approx = (after_date - first).days // (rule.interval * 7)
    elif freq is Frequency.MONTHLY:
        months = (after_date.year - first.year) * 12 + (after_date.month - first.month)
        approx = months // rule.interval
    elif freq is Frequency.QUARTERLY:
        months = (after_date.year - first.year) * 12 + (after_date.month - first.month)
        approx = months // (rule.interval * 3)
    elif freq is Frequency.YEARLY:
        months = (after_date.year - first.year) * 12 + (after_date.month - first.month)
        approx = months // (rule.interval * 12)
    else:  # pragma: no cover - guarded by nth_occurrence
        raise ValidationError(f"Unsupported frequency: {freq}")

    n = max(1, approx)
    # Walk back to be safe, then forward to the first index past after_date.
    while n > 1 and nth_occurrence(rule, n - 1) > after_date:
        n -= 1
    while nth_occurrence(rule, n) <= after_date:
        n += 1
    return n


@dataclass(frozen=True)
class NextOccurrence:
    """The outcome of planning the next occurrence of a series."""

    date: date | None
    skipped: int = 0
    exhausted: bool = False
    bounded: bool = False


def plan_next(
    rule: RecurrenceRule,
    after_date: date,
    *,
    today: date | None = None,
    max_fast_forward: int = MAX_FAST_FORWARD,
) -> NextOccurrence:
    """Plan the successor occurrence strictly after ``after_date``.

    * ``exhausted`` is set when an end condition (count/date) forbids any
      further occurrence.
    * When ``today`` is supplied, occurrences that fall before ``today`` are
      skipped (no backfill) and counted in ``skipped``.
    * ``bounded`` is set if fast-forwarding hit the safety limit.
    """
    if not rule.active:
        return NextOccurrence(date=None, exhausted=True)

    generated = rule.occurrences_generated
    n = _occurrence_index_after(rule, after_date)
    candidate = nth_occurrence(rule, n)
    skipped = 0

    while True:
        if rule.end_type is EndType.ON_DATE and rule.end_date is not None and candidate > rule.end_date:
            return NextOccurrence(date=None, skipped=skipped, exhausted=True)
        if rule.end_type is EndType.COUNT and rule.end_count is not None and generated >= rule.end_count:
            return NextOccurrence(date=None, skipped=skipped, exhausted=True)

        if today is None or candidate >= today:
            return NextOccurrence(date=candidate, skipped=skipped)

        # This occurrence was missed: fast-forward without generating a task.
        generated += 1
        skipped += 1
        if skipped >= max_fast_forward:
            return NextOccurrence(date=None, skipped=skipped, bounded=True)
        n += 1
        candidate = nth_occurrence(rule, n)


def preview(
    rule: RecurrenceRule,
    *,
    count: int = DEFAULT_PREVIEW_COUNT,
    after_date: date | None = None,
) -> list[date]:
    """Return the next ``count`` occurrence dates strictly after ``after_date``.

    Respects end conditions.  Used by the recurrence preview use case.
    """
    if count < 1:
        raise ValidationError("Preview count must be >= 1")
    start = after_date if after_date is not None else first_occurrence(rule) - timedelta(days=1)
    results: list[date] = []
    cursor = start
    generated = rule.occurrences_generated
    for _ in range(count):
        plan = plan_next(rule, cursor, today=None)
        if plan.date is None:
            break
        if rule.end_type is EndType.COUNT and rule.end_count is not None and generated >= rule.end_count:
            break
        results.append(plan.date)
        generated += 1
        cursor = plan.date
    return results
