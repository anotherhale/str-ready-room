"""Provider-independent calendar domain: value objects and iCalendar parsing.

This module contains **no** HTTP, WebDAV, ORM, or vendor code.  It knows the
iCalendar interchange format (RFC 5545) and nothing else, so any adapter that
speaks iCalendar (CalDAV, a file, a future Google adapter that renders iCal)
can reuse it.

Time handling is deliberately explicit:

* an event's ``start``/``end`` are stored as **timezone-aware** datetimes when
  the payload carries a ``TZID`` or a UTC marker, and as **naive** datetimes when
  it carries a floating local time;
* all-day events are anchored to a **date**, not a time.

The seed builds events with aware local datetimes (see DECISIONS D-029) so a
07:30 local wall-clock time survives the round trip instead of being silently
read as 07:30 UTC.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..domain.shared.errors import ValidationError

#: iCalendar line folding is 75 octets; we fold conservatively at 73 characters.
_FOLD_AT = 73


@dataclass(frozen=True)
class CalendarInfo:
    """A calendar (a named collection of events) as the provider sees it."""

    id: str
    name: str
    color: str | None = None


@dataclass
class CalendarEvent:
    """A provider-independent calendar event.

    ``uid`` is the event's stable identity *within* a calendar; ``calendar_id``
    is the provider's canonical id for the calendar that holds it.  Together they
    are the cache key (see DECISIONS D-032).
    """

    uid: str
    calendar_id: str
    summary: str
    start: datetime
    end: datetime | None = None
    all_day: bool = False
    location: str | None = None
    description: str | None = None
    #: Provider href, when the provider addresses events by URL (CalDAV does).
    href: str | None = None
    #: Set by the application service when the event is turned into a task.
    task_id: str | None = None
    #: iCalendar SEQUENCE; used to detect which copy of an event is newer.
    sequence: int = 0
    #: DTSTAMP (naive UTC) of the last provider-side modification, when known.
    updated_at: datetime | None = None

    @property
    def local_date(self) -> date:
        """The calendar date this event falls on, in its own zone (or floating)."""
        return self.start.date()

    def duration(self) -> timedelta:
        if self.end is None:
            return timedelta(0)
        return self.end - self.start


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def parse_calendar(text: str, *, calendar_id: str, href: str | None = None) -> CalendarEvent:
    """Parse a single VEVENT from iCalendar text.

    Tolerates the small structural variations real providers emit (``\r\n`` vs
    ``\n``, folded lines, ``DTSTART;VALUE=DATE`` all-day events).
    """
    if "BEGIN:VEVENT" not in text:
        raise ValidationError("iCalendar payload contains no VEVENT")

    props = _unfold_properties(_extract_vevent(text))
    uid = props.get("UID")
    if not uid:
        raise ValidationError("iCalendar event is missing UID")

    all_day = False
    raw_start = props.get("DTSTART")
    if raw_start is None:
        raise ValidationError("iCalendar event is missing DTSTART")
    start, start_is_date = _parse_datetime(raw_start, props.get("DTSTART;TZID"))
    if props.get("DTSTART;VALUE") == "DATE" or props.get("DTSTART;ISDATE") == "1":
        start_is_date = True
    all_day = start_is_date

    end: datetime | None = None
    if props.get("DTEND") is not None:
        parsed_end, _ = _parse_datetime(props["DTEND"], props.get("DTEND;TZID"))
        end = parsed_end

    sequence = 0
    if props.get("SEQUENCE"):
        try:
            sequence = int(props["SEQUENCE"])
        except ValueError:
            sequence = 0

    updated_at = None
    if props.get("DTSTAMP"):
        try:
            stamp, _ = _parse_datetime(props["DTSTAMP"], None)
            updated_at = _as_naive_utc(stamp)
        except ValidationError:
            updated_at = None

    return CalendarEvent(
        uid=uid,
        calendar_id=calendar_id,
        summary=_unescape_text(props.get("SUMMARY", "")) or "(untitled event)",
        start=start,
        end=end,
        all_day=all_day,
        location=_unescape_text(props["LOCATION"]) if props.get("LOCATION") else None,
        description=_unescape_text(props["DESCRIPTION"]) if props.get("DESCRIPTION") else None,
        href=href,
        sequence=sequence,
        updated_at=updated_at,
    )


def serialize_calendar(event: CalendarEvent, *, tz: ZoneInfo | None = None) -> str:
    """Serialize an event to an iCalendar VEVENT.

    Aware datetimes are written with their ``TZID`` so the wall-clock time is
    preserved; a naive datetime is treated as UTC (an explicit, documented rule
    rather than an accident).
    """
    zone = tz
    if zone is None and event.start.tzinfo is not None:
        zone = event.start.tzinfo  # type: ignore[assignment]

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//READY ROOM//EN", "BEGIN:VEVENT"]
    lines.append(f"UID:{event.uid}")
    lines.append(f"DTSTAMP:{_format_utc(event.updated_at or datetime.now(UTC))}")
    lines.append(f"SEQUENCE:{event.sequence}")
    lines.append(f"SUMMARY:{_escape_text(event.summary)}")

    if event.all_day:
        lines.append(f"DTSTART;VALUE=DATE:{event.start.date().strftime('%Y%m%d')}")
        end_date = (event.end or (event.start + timedelta(days=1))).date()
        lines.append(f"DTEND;VALUE=DATE:{end_date.strftime('%Y%m%d')}")
    else:
        lines.append(_format_datetime("DTSTART", event.start, zone))
        if event.end is not None:
            lines.append(_format_datetime("DTEND", event.end, zone))

    if event.location:
        lines.append(f"LOCATION:{_escape_text(event.location)}")
    if event.description:
        lines.append(f"DESCRIPTION:{_escape_text(event.description)}")

    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\r\n".join(lines) + "\r\n"


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _extract_vevent(text: str) -> str:
    """Return only the first VEVENT block.

    A VCALENDAR may also carry a VTIMEZONE, whose own ``DTSTART`` lines describe
    the zone's historical transitions.  Parsing the whole payload would let those
    leak in as the event's start, so scope the property scan to the event itself.
    """
    start = text.find("BEGIN:VEVENT")
    if start == -1:
        return text
    end = text.find("END:VEVENT", start)
    if end == -1:
        return text[start:]
    return text[start : end + len("END:VEVENT")]


def _unfold_properties(text: str) -> dict[str, str]:
    """Unfold folded lines and return ``{PROPERTY;PARAM: value}``.

    A property with parameters is keyed both as the bare name and as
    ``NAME;PARAM`` so callers can look up either.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    unfolded: list[str] = []
    for line in normalized.split("\n"):
        if line[:1] in (" ", "\t") and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    props: dict[str, str] = {}
    for line in unfolded:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        name, _, params = key.partition(";")
        props.setdefault(name.strip().upper(), value.strip())
        if params:
            props[f"{name.strip().upper()};{params.strip().upper()}"] = value.strip()
            for param in params.split(";"):
                if param.upper().startswith("TZID="):
                    props[f"{name.strip().upper()};TZID"] = param.split("=", 1)[1]
                if param.upper() == "VALUE=DATE":
                    props[f"{name.strip().upper()};VALUE"] = "DATE"
    return props


def _parse_datetime(value: str, tzid: str | None) -> tuple[datetime, bool]:
    """Parse an iCalendar date or datetime.  Returns (value, is_date)."""
    value = value.strip()
    if len(value) == 8 and value.isdigit():  # DATE: YYYYMMDD
        return datetime.strptime(value, "%Y%m%d"), True

    if value.endswith("Z"):
        parsed = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        return parsed, False

    parsed = datetime.strptime(value, "%Y%m%dT%H%M%S")
    if tzid:
        try:
            return parsed.replace(tzinfo=ZoneInfo(tzid)), False
        except Exception as exc:  # noqa: BLE001
            raise ValidationError(f"Unknown TZID in event: {tzid!r}") from exc
    # Floating local time: keep it naive rather than inventing a zone.
    return parsed, False


def _format_datetime(prop: str, value: datetime, zone: ZoneInfo | None) -> str:
    if value.tzinfo is not None:
        zone = value.tzinfo  # type: ignore[assignment]
    # Only a ZoneInfo carries an IANA ``key``; a fixed offset (including UTC)
    # cannot be named as a TZID, so it is written as a UTC instant instead.
    key = getattr(zone, "key", None)
    if key is not None:
        local = value.astimezone(zone) if value.tzinfo is not None else value
        return f"{prop};TZID={key}:{local.strftime('%Y%m%dT%H%M%S')}"
    # Naive input or a fixed-offset zone: write an unambiguous UTC instant.
    return f"{prop}:{_format_utc(value)}"


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _unescape_text(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def fold_line(line: str) -> str:
    """Fold a single logical line at 73 characters (used by tests/tools)."""
    if len(line) <= _FOLD_AT:
        return line
    chunks = [line[i : i + _FOLD_AT] for i in range(0, len(line), _FOLD_AT)]
    return "\r\n ".join(chunks)
