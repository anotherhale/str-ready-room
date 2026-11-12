"""Application configuration.

Reads from environment variables (prefix ``READY_ROOM_``) with sensible demo
defaults.  This is the only place environment values are read.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Curated shortlist of IANA zones offered in the Settings selector.  Validation
#: still accepts any real IANA identifier, so this is a convenience, not a
#: restriction.  A full list of ~600 zones would overwhelm a single operator.
COMMON_TIMEZONES: tuple[str, ...] = (
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Anchorage",
    "America/Phoenix",
    "Pacific/Honolulu",
    "America/Puerto_Rico",
    "Pacific/Guam",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Asia/Seoul",
    "Asia/Singapore",
    "Asia/Dubai",
    "Australia/Sydney",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="READY_ROOM_", env_file=None, extra="ignore")

    # --- runtime -----------------------------------------------------
    environment: str = "demo"

    # --- database ----------------------------------------------------
    db_adapter: str = "sqlalchemy"
    database_url: str = "sqlite:////data/ready_room.db"

    # --- identity (single-user demo adapter) -------------------------
    auth_provider: str = "single_user"
    operator_id: str = "maverick"
    operator_display_name: str = "Maverick"
    default_timezone: str = "America/Denver"

    # --- authorization ----------------------------------------------
    authorization_engine: str = "policy"

    # --- calendar integration (optional; best-effort) ----------------
    # Disable with READY_ROOM_CALENDAR_PROVIDER=none; the rest of the app is
    # unaffected when the provider is off or unreachable.
    calendar_provider: str = "none"
    caldav_url: str = "http://radicale:5232"
    caldav_username: str = "maverick"
    caldav_password: str = "readyroom"
    caldav_calendar: str = "detachment"
    calendar_sync_on_startup: bool = True

    # --- email integration (optional; read-only, best-effort) --------
    email_provider: str = "none"
    imap_host: str = "greenmail"
    imap_port: int = 3143
    # The mailbox is addressed by its *full* address; GreenMail creates a
    # different mailbox for the bare local part (see DECISIONS D-027).
    imap_username: str = "maverick@detachment.demo"
    imap_password: str = "readyroom"
    imap_mailbox: str = "INBOX"
    email_seed_on_startup: bool = True
    # SMTP is used only by the seeder/demo script, never by the request path.
    smtp_host: str = "greenmail"
    smtp_port: int = 3025

    # --- seed --------------------------------------------------------
    seed_on_startup: bool = True

    # --- deterministic clock (test/demo aid) -------------------------
    # When set (ISO-8601 UTC, e.g. "2026-03-10T13:00:00"), the app uses a fixed
    # clock instead of the system clock.  Left unset in normal operation.
    fixed_now_utc: str | None = None

    # --- CORS (local development convenience; nginx is same-origin) --
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
