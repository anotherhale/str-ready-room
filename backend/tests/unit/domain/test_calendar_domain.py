"""Unit tests for the provider-independent calendar domain (iCalendar).

Pure: no database, no network, no HTTP.  Covers the round trip, TZID handling,
all-day events, and the line-folding tolerance real providers rely on.
"""
from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.calendar.domain import (
    CalendarEvent,
    fold_line,
    parse_calendar,
    serialize_calendar,
)
from app.domain.shared.errors import ValidationError


def test_parse_utc_datetime():
    text = (
        "BEGIN:VCALENDAR\nBEGIN:VEVENT\n"
        "UID:abc\nDTSTART:20260310T130000Z\nDTEND:20260310T140000Z\n"
        "SUMMARY:Flight quarters\nEND:VEVENT\nEND:VCALENDAR\n"
    )
    event = parse_calendar(text, calendar_id="cal")
    assert event.uid == "abc"
    assert event.summary == "Flight quarters"
    assert event.start == datetime(2026, 3, 10, 13, 0, tzinfo=UTC)
    assert event.start.tzinfo is not None
    assert not event.all_day


def test_parse_tzid_datetime_preserves_wall_clock():
    text = (
        "BEGIN:VEVENT\nUID:abc\nDTSTART;TZID=America/New_York:20260310T073000\n"
        "SUMMARY:Quarters\nEND:VEVENT"
    )
    event = parse_calendar(text, calendar_id="cal")
    local = event.start.astimezone(ZoneInfo("America/New_York"))
    assert (local.hour, local.minute) == (7, 30)
    assert event.start.tzinfo is not None


def test_parse_all_day_event_uses_date():
    text = "BEGIN:VEVENT\nUID:a\nDTSTART;VALUE=DATE:20260310\nSUMMARY:Standup\nEND:VEVENT"
    event = parse_calendar(text, calendar_id="cal")
    assert event.all_day is True
    assert event.start.date().isoformat() == "2026-03-10"


def test_parse_tolerates_folded_lines_and_crlf():
    text = (
        "BEGIN:VEVENT\r\nUID:a\r\nDTSTART:20260310T130000Z\r\n"
        "SUMMARY:A very long summary that has been\r\n  folded across lines\r\nEND:VEVENT\r\n"
    )
    event = parse_calendar(text, calendar_id="cal")
    assert event.summary == "A very long summary that has been folded across lines"


def test_parse_ignores_vtimezone_dtstart():
    """A VTIMEZONE block carries its own DTSTART lines; they must not leak in."""
    text = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VTIMEZONE\nTZID:America/New_York\n"
        "BEGIN:STANDARD\nDTSTART:20001029T020000\nTZNAME:EST\n"
        "TZOFFSETFROM:-0400\nTZOFFSETTO:-0500\nEND:STANDARD\nEND:VTIMEZONE\n"
        "BEGIN:VEVENT\nUID:z1\nDTSTART;TZID=America/New_York:20260310T073000\n"
        "DTEND;TZID=America/New_York:20260310T081500\nSUMMARY:Quarters\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    event = parse_calendar(text, calendar_id="cal")
    local = event.start.astimezone(ZoneInfo("America/New_York"))
    assert local.date().isoformat() == "2026-03-10"
    assert (local.hour, local.minute) == (7, 30)


def test_parse_missing_uid_raises():
    with pytest.raises(ValidationError):
        parse_calendar("BEGIN:VEVENT\nDTSTART:20260310T130000Z\nEND:VEVENT", calendar_id="cal")


def test_parse_unknown_tzid_raises():
    text = "BEGIN:VEVENT\nUID:a\nDTSTART;TZID=Mars/Olympus:20260310T073000\nEND:VEVENT"
    with pytest.raises(ValidationError):
        parse_calendar(text, calendar_id="cal")


def test_round_trip_preserves_local_wall_clock():
    zone = ZoneInfo("America/New_York")
    original = CalendarEvent(
        uid="round-trip",
        calendar_id="cal",
        summary="Morning brief",
        start=datetime(2026, 3, 10, 7, 30, tzinfo=zone),
        end=datetime(2026, 3, 10, 8, 15, tzinfo=zone),
        location="Ready room",
        description="Line one\nLine two",
    )
    serialized = serialize_calendar(original)
    parsed = parse_calendar(serialized, calendar_id="cal")

    local_start = parsed.start.astimezone(zone)
    assert (local_start.hour, local_start.minute) == (7, 30)
    assert parsed.summary == "Morning brief"
    assert parsed.location == "Ready room"
    assert parsed.description == "Line one\nLine two"


def test_serialize_escapes_commas_and_semicolons():
    event = CalendarEvent(
        uid="x",
        calendar_id="cal",
        summary="Alpha, Bravo; Charlie",
        start=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
    )
    serialized = serialize_calendar(event)
    assert "Alpha\\, Bravo\\; Charlie" in serialized
    assert parse_calendar(serialized, calendar_id="cal").summary == "Alpha, Bravo; Charlie"


def test_serialize_all_day_uses_date_value():
    event = CalendarEvent(
        uid="x",
        calendar_id="cal",
        summary="Admin day",
        start=datetime(2026, 3, 10),
        all_day=True,
    )
    serialized = serialize_calendar(event)
    assert "DTSTART;VALUE=DATE:20260310" in serialized


def test_fold_line_wraps_long_lines():
    folded = fold_line("SUMMARY:" + "x" * 200)
    assert "\r\n " in folded
    assert folded.startswith("SUMMARY:")
