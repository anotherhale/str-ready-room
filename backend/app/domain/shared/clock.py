"""Clock abstraction.

Domain and application code depend on this port instead of calling
``datetime.now`` directly, which keeps date/time behaviour deterministic in
tests.  ``zoneinfo`` requires the ``tzdata`` package at runtime.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from .errors import ValidationError


class Clock(Protocol):
    """Port for reading the current time."""

    def now_utc(self) -> datetime:
        """Return the current time as a *naive* UTC datetime."""

    def today(self, timezone_name: str) -> date:
        """Return the operator's local calendar date for the given timezone."""


def normalize_utc(value: datetime) -> datetime:
    """Coerce an aware datetime to naive UTC; pass naive datetimes through."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def resolve_today(now: datetime, timezone_name: str) -> date:
    """Resolve the local calendar date for an instant.

    Handles UTC rollover correctly: an instant at ``23:30Z`` is still the
    previous day for an operator in ``America/New_York``.
    """
    try:
        zone = ZoneInfo(timezone_name)
    except Exception as exc:  # noqa: BLE001 - surface a domain error
        raise ValidationError(f"Unknown timezone: {timezone_name!r}") from exc
    aware = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return aware.astimezone(zone).date()


class SystemClock:
    """Production clock backed by the operating system."""

    def now_utc(self) -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    def today(self, timezone_name: str) -> date:
        return resolve_today(self.now_utc(), timezone_name)


class FixedClock:
    """Deterministic clock for tests."""

    def __init__(self, now: datetime) -> None:
        self._now = normalize_utc(now)

    def now_utc(self) -> datetime:
        return self._now

    def today(self, timezone_name: str) -> date:
        return resolve_today(self._now, timezone_name)
