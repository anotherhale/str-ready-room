"""Calendar cache entities.

The application keeps its **own** copy of provider events so the dashboard and
Calendar view never depend on the calendar server being up (see DECISIONS D-025).
``CalendarEventRecord`` is that cached row; it carries the provider's ``href``,
the last-seen ``sequence``, and an optional ``task_id`` link set when the event
is captured into a responsibility (see DECISIONS D-030).

Wall-clock fidelity (DECISIONS D-029): an event's ``start``/``end`` are stored as
naive UTC alongside the IANA ``timezone`` it is anchored to, so a 07:30 local
event is read back as 07:30 local rather than 07:30 UTC.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from .domain import CalendarEvent


@dataclass
class CalendarEventRecord:
    """A cached calendar event."""

    id: str
    owner_id: str
    uid: str
    calendar_id: str
    summary: str
    start: datetime  # naive UTC
    end: datetime | None  # naive UTC
    all_day: bool = False
    location: str | None = None
    description: str | None = None
    href: str | None = None
    task_id: str | None = None
    sequence: int = 0
    #: IANA zone the event is anchored to, or ``None`` for a floating event.
    timezone: str | None = None
    #: When this row was last refreshed from the provider (naive UTC).
    synced_at: datetime | None = None

    @property
    def local_date(self) -> date:
        return self.start_local().date()

    def start_local(self) -> datetime:
        return _to_local(self.start, self.timezone)

    def end_local(self) -> datetime | None:
        return _to_local(self.end, self.timezone) if self.end is not None else None

    def to_event(self) -> CalendarEvent:
        """Reconstruct the provider-independent event (aware local datetimes)."""
        return CalendarEvent(
            uid=self.uid,
            calendar_id=self.calendar_id,
            summary=self.summary,
            start=self.start_local(),
            end=self.end_local(),
            all_day=self.all_day,
            location=self.location,
            description=self.description,
            href=self.href,
            task_id=self.task_id,
            sequence=self.sequence,
            updated_at=self.synced_at,
        )

    @classmethod
    def from_event(
        cls,
        event: CalendarEvent,
        *,
        id: str,
        owner_id: str,
        synced_at: datetime,
    ) -> CalendarEventRecord:
        timezone_name = _zone_name(event.start)
        return cls(
            id=id,
            owner_id=owner_id,
            uid=event.uid,
            calendar_id=event.calendar_id,
            summary=event.summary,
            start=_to_naive_utc(event.start),
            end=_optional_naive_utc(event.end),
            all_day=event.all_day,
            location=event.location,
            description=event.description,
            href=event.href,
            task_id=event.task_id,
            sequence=event.sequence,
            timezone=timezone_name,
            synced_at=synced_at,
        )


def _zone_name(value: datetime | None) -> str | None:
    if value is None or value.tzinfo is None:
        return None
    key = getattr(value.tzinfo, "key", None)
    return key


def _to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _optional_naive_utc(value: datetime | None) -> datetime | None:
    return _to_naive_utc(value) if value is not None else None


def _to_local(value: datetime, timezone_name: str | None) -> datetime:
    if timezone_name is None:
        return value
    try:
        zone = ZoneInfo(timezone_name)
    except Exception:  # noqa: BLE001 - unknown zone: fall back to naive
        return value
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(zone)
