"""The calendar provider port.

The application service depends only on this interface.  A concrete adapter
(CalDAV today; a Google or Microsoft adapter later) implements it and is chosen
in the registry from configuration.

The port sits at the level the application cares about — "list calendars",
"list events", "create/delete an event" — not at the socket or HTTP-verb level,
so an adapter that speaks a different protocol is a drop-in replacement.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ...domain.shared.errors import IntegrationError
from ..domain import CalendarEvent, CalendarInfo


class CalendarError(IntegrationError):
    """A calendar provider failure, translated for the application layer.

    Inherits the domain ``IntegrationError`` so the single FastAPI error handler
    maps it (using its ``status`` hint) without importing this adapter.
    """

    code = "calendar_error"


class CalendarProvider(ABC):
    """Port: a source of calendars and events."""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def list_calendars(self) -> list[CalendarInfo]:
        """Return the calendars this provider exposes."""

    @abstractmethod
    def list_events(self, calendar_id: str) -> list[CalendarEvent]:
        """Return every event in a calendar."""

    @abstractmethod
    def create_event(self, event: CalendarEvent) -> CalendarEvent:
        """Create an event, returning it with its provider href set."""

    @abstractmethod
    def delete_event(self, calendar_id: str, uid: str, href: str | None = None) -> None:
        """Delete an event by uid (or href, when the provider needs it)."""

    def resolve_calendar_id(self, calendar_ref: str) -> str:
        """Map a friendly name or bare path to the provider's canonical id.

        The default is identity: a provider whose ids already match what the
        caller supplies needs no override.  CalDAV overrides this to map
        ``"detachment"`` to ``"/maverick/detachment/"`` so a locally created
        event is cached under the same key ``list_events`` will later return
        (see DECISIONS D-032).
        """
        return calendar_ref

    def health(self) -> bool:
        """Best-effort reachability probe.  Never raises."""
        try:
            self.list_calendars()
            return True
        except Exception:  # noqa: BLE001 - a probe must not raise
            return False
