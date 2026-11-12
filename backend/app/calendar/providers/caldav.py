"""CalDAV adapter for a self-hosted Radicale server.

All WebDAV/HTTP detail lives here.  The verbs we need — ``PROPFIND``, ``REPORT``,
``MKCOL``, ``PUT``, ``DELETE`` — are simple enough to drive with the standard
library (``urllib`` + ``xml.etree``), which keeps the runtime dependency count
at zero (see DECISIONS D-025).

The adapter returns and accepts provider-independent ``CalendarEvent`` objects;
iCalendar parsing/serialization is shared with every other adapter via
``calendar.domain``.
"""
from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from ...domain.shared.errors import ValidationError
from ..domain import CalendarEvent, CalendarInfo, parse_calendar, serialize_calendar
from .base import CalendarError, CalendarProvider

_DAV = "DAV:"
_CALDAV = "urn:ietf:params:xml:ns:caldav"


class CalDavCalendarProvider(CalendarProvider):
    """A CalDAV provider targeting a Radicale collection.

    ``base_url`` is the CalDAV root (e.g. ``http://radicale:5232``); ``username``
    and ``password`` authenticate every request.  ``default_calendar`` is the
    collection the app reads from and writes to by default.
    """

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        default_calendar: str,
        timeout: float = 10.0,
    ) -> None:
        if not base_url:
            raise ValidationError("CalDAV base_url is required")
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._default_calendar = default_calendar
        self._timeout = timeout

    # -- port ----------------------------------------------------------
    def list_calendars(self) -> list[CalendarInfo]:
        body = (
            '<?xml version="1.0" encoding="utf-8" ?>'
            '<d:propfind xmlns:d="DAV:"><d:prop>'
            "<d:displayname/><d:resourcetype/>"
            "</d:prop></d:propfind>"
        )
        # Calendars live under the principal home collection (Radicale exposes
        # them at ``/<user>/<calendar>/``), so search there as well as the root.
        roots = [f"{self._base_url}/"]
        home = self._principal_home()
        if home and home != f"{self._base_url}":
            roots.append(f"{home}/")

        calendars: list[CalendarInfo] = []
        seen: set[str] = set()
        for root in roots:
            status, text = self._request("PROPFIND", root, body=body, depth="1")
            if status not in (200, 207):
                raise CalendarError(f"CalDAV PROPFIND failed with status {status}", status=502)
            for response in _iter_responses(text):
                href = _first_text(response, "href")
                resource_type = response.find(".//{DAV:}resourcetype")
                is_calendar = (
                    resource_type is not None
                    and resource_type.find(f"{{{_CALDAV}}}calendar") is not None
                )
                if not href or not is_calendar or href in seen:
                    continue
                seen.add(href)
                display = _first_text(response, "displayname") or href
                calendars.append(CalendarInfo(id=href, name=display))
        return calendars

    def list_events(self, calendar_id: str) -> list[CalendarEvent]:
        url = self._calendar_url(calendar_id)
        body = (
            '<?xml version="1.0" encoding="utf-8" ?>'
            '<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
            "<d:prop><d:getetag/><c:calendar-data/></d:prop>"
            "<c:filter><c:comp-filter name=\"VCALENDAR\">"
            "<c:comp-filter name=\"VEVENT\"/></c:comp-filter></c:filter>"
            "</c:calendar-query>"
        )
        status, text = self._request("REPORT", url, body=body, depth="1")
        if status not in (200, 207):
            raise CalendarError(f"CalDAV REPORT failed with status {status}", status=502)

        events: list[CalendarEvent] = []
        for response in _iter_responses(text):
            raw_href = _first_text(response, "href")
            # Cache an absolute href: CalDAV returns a server-relative path
            # (e.g. /maverick/detachment/x.ics) that urllib cannot open directly.
            href = self._absolute(raw_href) if raw_href else None
            data = _first_text(response, "calendar-data", _CALDAV)
            if not data:
                continue
            try:
                events.append(parse_calendar(data, calendar_id=calendar_id, href=href))
            except ValidationError:
                # A malformed event must not break the whole sync.
                continue
        return events

    def create_event(self, event: CalendarEvent) -> CalendarEvent:
        calendar_id = self.resolve_calendar_id(event.calendar_id or self._default_calendar)
        calendar_url = self._calendar_url(calendar_id)
        href = event.href or f"{calendar_url}{quote(event.uid)}.ics"
        tz = ZoneInfo(self._default_timezone_hint) if self._default_timezone_hint else None
        payload = serialize_calendar(event, tz=tz)
        status, _ = self._request(
            "PUT",
            href,
            body=payload,
            headers={"Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"},
        )
        if status not in (200, 201, 204):
            if status == 412:
                raise CalendarError(
                    "An event with that identity already exists", status=409, code="conflict"
                )
            raise CalendarError(f"CalDAV PUT failed with status {status}", status=502)
        event.href = href
        event.calendar_id = calendar_id
        return event

    def delete_event(self, calendar_id: str, uid: str, href: str | None = None) -> None:
        target = self._absolute(href) if href else f"{self._calendar_url(calendar_id)}{quote(uid)}.ics"
        status, _ = self._request("DELETE", target)
        if status not in (200, 204, 404):
            raise CalendarError(f"CalDAV DELETE failed with status {status}", status=502)

    def resolve_calendar_id(self, calendar_ref: str) -> str:
        """Map ``"detachment"`` (or a bare path) to the provider's canonical id.

        Radicale only lets a client create a calendar *inside* its principal
        home collection, so this discovers the principal, then creates the
        collection on demand with ``MKCALENDAR`` (idempotent) and returns the
        canonical path.  Providers that need no such step override to identity.
        """
        if not calendar_ref:
            calendar_ref = self._default_calendar
        # An already-absolute URL is a canonical id we produced earlier; it must
        # be used as-is, never re-prefixed with the principal home (which would
        # yield a nonsense path like ``/maverick/http://host/maverick/cal/``).
        if calendar_ref.startswith(("http://", "https://")):
            return calendar_ref if calendar_ref.endswith("/") else f"{calendar_ref}/"
        if calendar_ref.startswith("/"):
            target = calendar_ref if calendar_ref.endswith("/") else f"{calendar_ref}/"
        else:
            home = self._principal_home() or f"{self._base_url}/"
            target = f"{home.rstrip('/')}/{calendar_ref.strip('/')}/"
        self._ensure_collection(target)
        return target

    def _principal_home(self) -> str | None:
        """Discover the current user's principal URL (its collection home)."""
        body = (
            '<?xml version="1.0" encoding="utf-8" ?>'
            '<d:propfind xmlns:d="DAV:"><d:prop><d:current-user-principal/></d:prop></d:propfind>'
        )
        try:
            status, text = self._request("PROPFIND", f"{self._base_url}/", body=body, depth="0")
        except CalendarError:
            return None
        if status not in (200, 207):
            return None
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return None
        node = root.find(".//{*}current-user-principal/{*}href")
        href = node.text if node is not None else None
        if not href:
            return None
        return urljoin(f"{self._base_url}/", href).rstrip("/")

    def _ensure_collection(self, url: str) -> None:
        """Create the calendar collection if it does not yet exist (idempotent)."""
        body = (
            '<?xml version="1.0" encoding="utf-8" ?>'
            '<c:mkcalendar xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
            "<d:set><d:prop><d:displayname/><c:supported-calendar-component-set>"
            '<c:comp name="VEVENT"/></c:supported-calendar-component-set>'
            "</d:prop></d:set></c:mkcalendar>"
        )
        status, _ = self._request(
            "MKCALENDAR",
            url,
            body=body,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
        # 201 created, 405 method-not-allowed, and 409 conflict (already exists
        # on Radicale) are all "fine to proceed"; a later PUT surfaces any
        # genuine failure.
        if status not in (200, 201, 204, 405, 409):
            raise CalendarError(f"CalDAV MKCALENDAR failed with status {status}", status=502)

    # -- wiring hooks --------------------------------------------------
    _default_timezone_hint: str | None = None

    def set_default_timezone(self, timezone_name: str) -> None:
        """Hint used when serializing a naive event (kept out of the port)."""
        self._default_timezone_hint = timezone_name

    # -- internals -----------------------------------------------------
    def _absolute(self, href: str) -> str:
        """Resolve a possibly server-relative href against the CalDAV base URL.

        ``list_events`` and ``resolve_calendar_id`` may return absolute URLs;
        a REPORT response returns a server-relative path. Both must become a
        URL urllib can open.
        """
        return href if href.startswith(("http://", "https://")) else urljoin(f"{self._base_url}/", href)

    def _calendar_url(self, calendar_id: str) -> str:
        """Absolute collection URL for a canonical id or a bare reference.

        ``resolve_calendar_id`` returns an absolute URL, so accept both shapes
        and never double-prefix the base URL.
        """
        ref = (calendar_id or self._default_calendar).strip()
        if ref.startswith(("http://", "https://")):
            return ref if ref.endswith("/") else f"{ref}/"
        return f"{self._base_url}/{ref.strip('/')}/"

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: str | None = None,
        depth: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        data = body.encode("utf-8") if body is not None else None
        request = Request(url, data=data, method=method)
        request.add_header("Authorization", self._auth_header())
        if depth is not None:
            request.add_header("Depth", depth)
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        try:
            with urlopen(request, timeout=self._timeout) as response:  # noqa: S310 - configured URL
                return response.status, response.read().decode("utf-8", "replace")
        except HTTPError as exc:
            payload = exc.read().decode("utf-8", "replace") if exc.fp else ""
            return exc.code, payload
        except (URLError, TimeoutError, OSError) as exc:
            raise CalendarError(f"CalDAV unreachable: {exc}", status=502) from exc

    def _auth_header(self) -> str:
        token = base64.b64encode(f"{self._username}:{self._password}".encode()).decode()
        return f"Basic {token}"


def _iter_responses(xml_text: str) -> list[ET.Element]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise CalendarError(f"CalDAV returned malformed XML: {exc}", status=502) from exc
    return root.findall(f".//{{{_DAV}}}response")


def _first_text(response: ET.Element, tag: str, namespace: str = _DAV) -> str | None:
    node = response.find(f".//{{{namespace}}}{tag}")
    if node is None:
        return None
    return node.text


def _join(base: str, href: str) -> str:  # pragma: no cover - helper
    return urljoin(base, href)


def _path_of(url: str) -> str:  # pragma: no cover - helper
    return urlparse(url).path
