"""CalDAV adapter URL handling.

These pin the shapes that a live Radicale actually enforces, using a fake
``_request`` so no network is touched.  They exist because the in-memory test
double normalises ids idempotently, which hid a real double-prefixing bug: a
canonical id (an absolute URL) was being re-prefixed with the principal home,
producing paths like ``/maverick/http://host/maverick/detachment/`` (403).
"""
from __future__ import annotations

from app.calendar.providers.caldav import CalDavCalendarProvider

BASE = "http://radicale:5232"


def _provider() -> CalDavCalendarProvider:
    return CalDavCalendarProvider(
        base_url=BASE,
        username="maverick",
        password="readyroom",
        default_calendar="detachment",
    )


def test_calendar_url_accepts_absolute_id_without_double_prefix():
    p = _provider()
    assert p._calendar_url(f"{BASE}/maverick/detachment/") == f"{BASE}/maverick/detachment/"
    assert p._calendar_url(f"{BASE}/maverick/detachment") == f"{BASE}/maverick/detachment/"


def test_calendar_url_prepends_base_for_bare_reference():
    p = _provider()
    assert p._calendar_url("detachment") == f"{BASE}/detachment/"
    assert p._calendar_url("/maverick/detachment/") == f"{BASE}/maverick/detachment/"


def test_resolve_calendar_id_does_not_double_prefix_absolute_id(monkeypatch):
    p = _provider()
    calls: list[str] = []

    def fake_request(method, url, **kwargs):  # noqa: ANN001
        calls.append(url)
        return 409, ""  # "already exists" -> proceed

    monkeypatch.setattr(p, "_request", fake_request)
    # The principal-home lookup runs first; stub it so we exercise only the
    # absolute-id path.
    monkeypatch.setattr(p, "_principal_home", lambda: f"{BASE}/maverick")

    resolved = p.resolve_calendar_id(f"{BASE}/maverick/detachment/")

    assert resolved == f"{BASE}/maverick/detachment/"
    # An absolute id is returned as-is: it was already ensured when first
    # produced, and the nonsense double-prefixed path must never be requested.
    assert calls == []


def test_resolve_calendar_id_builds_under_principal_home(monkeypatch):
    p = _provider()
    calls: list[str] = []

    def fake_request(method, url, **kwargs):  # noqa: ANN001
        calls.append(url)
        return 201, ""

    monkeypatch.setattr(p, "_request", fake_request)
    monkeypatch.setattr(p, "_principal_home", lambda: f"{BASE}/maverick")

    resolved = p.resolve_calendar_id("detachment")

    assert resolved == f"{BASE}/maverick/detachment/"
    assert calls == [f"{BASE}/maverick/detachment/"]


def test_absolute_resolves_server_relative_href():
    p = _provider()
    # CalDAV REPORT responses carry a server-relative path.
    assert p._absolute("/maverick/detachment/x.ics") == f"{BASE}/maverick/detachment/x.ics"


def test_absolute_passes_through_absolute_url():
    p = _provider()
    assert p._absolute(f"{BASE}/maverick/detachment/x.ics") == f"{BASE}/maverick/detachment/x.ics"


def test_delete_event_resolves_relative_href_before_request(monkeypatch):
    # Regression: a cached relative href was handed to urllib unchanged, which
    # raised "unknown url type" -> HTTP 500 on delete.
    p = _provider()
    calls: list[str] = []

    def fake_request(method, url, **kwargs):  # noqa: ANN001
        calls.append(url)
        return 204, ""

    monkeypatch.setattr(p, "_request", fake_request)
    p.delete_event("detachment", "uid-1", href="/maverick/detachment/uid-1.ics")

    assert calls == [f"{BASE}/maverick/detachment/uid-1.ics"]
