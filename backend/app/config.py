"""Application configuration.

Reads from environment variables (prefix ``READY_ROOM_``) with sensible demo
defaults.  This is the only place environment values are read.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    default_timezone: str = "America/New_York"

    # --- authorization ----------------------------------------------
    authorization_engine: str = "policy"

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
