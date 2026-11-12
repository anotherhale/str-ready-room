"""Calendar provider factory.

The single place a concrete calendar adapter is chosen from configuration.  A
new backend (Google, Microsoft, a local file) is added here and selected with
``READY_ROOM_CALENDAR_PROVIDER`` without touching the domain, application
services, API, or UI.
"""
from __future__ import annotations

from ...config import Settings
from .base import CalendarProvider
from .caldav import CalDavCalendarProvider

#: Providers that mean "calendar integration is switched off".
DISABLED = {"", "none", "disabled", "off"}


def build_calendar_provider(settings: Settings) -> CalendarProvider | None:
    """Return the configured provider, or ``None`` when disabled.

    The integration is optional: an unknown provider name is a configuration
    error, but a disabled one simply means the Calendar view reports
    "unavailable" and the rest of READY ROOM is unaffected.
    """
    choice = (settings.calendar_provider or "").strip().lower()
    if choice in DISABLED:
        return None
    if choice == "caldav":
        return CalDavCalendarProvider(
            base_url=settings.caldav_url,
            username=settings.caldav_username,
            password=settings.caldav_password,
            default_calendar=settings.caldav_calendar,
        )
    raise ValueError(
        f"Unknown calendar provider {settings.calendar_provider!r}. "
        "Supported: caldav, none."
    )
