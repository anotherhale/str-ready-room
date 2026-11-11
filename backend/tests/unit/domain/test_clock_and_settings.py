"""Clock / timezone resolution tests, including UTC rollover."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.domain.settings.entities import OperatorSettings, validate_timezone
from app.domain.shared.clock import FixedClock, resolve_today
from app.domain.shared.errors import ValidationError
from app.domain.tasks.value_objects import category_key, normalize_category


def test_resolve_today_utc_rollover_previous_local_day():
    # 03:30Z on the 11th is still the 10th in New York (UTC-4 in DST).
    instant = datetime(2026, 7, 11, 3, 30, 0)
    assert resolve_today(instant, "America/New_York") == date(2026, 7, 10)
    assert resolve_today(instant, "UTC") == date(2026, 7, 11)


def test_resolve_today_rollover_forward():
    # 23:30Z on the 10th is already the 11th in Tokyo (UTC+9).
    instant = datetime(2026, 3, 10, 23, 30, 0)
    assert resolve_today(instant, "Asia/Tokyo") == date(2026, 3, 11)


def test_resolve_today_rejects_unknown_zone():
    with pytest.raises(ValidationError):
        resolve_today(datetime(2026, 1, 1), "Mars/Olympus_Mons")


def test_fixed_clock_is_deterministic():
    clock = FixedClock(datetime(2026, 3, 10, 3, 0, 0))
    assert clock.now_utc() == datetime(2026, 3, 10, 3, 0, 0)
    assert clock.today("America/New_York") == date(2026, 3, 9)


def test_settings_validate_timezone_and_window():
    settings = OperatorSettings(owner_id="op-1", warning_window_days=5, timezone="America/Chicago")
    assert settings.warning_window_days == 5
    with pytest.raises(ValidationError):
        OperatorSettings(owner_id="op-1", warning_window_days=0)
    with pytest.raises(ValidationError):
        OperatorSettings(owner_id="op-1", timezone="Not/AZone")


def test_validate_timezone_returns_name():
    assert validate_timezone("UTC") == "UTC"


def test_category_normalization_and_key():
    assert normalize_category("  Flight   Administration ") == "Flight Administration"
    assert category_key("flight administration") == category_key("FLIGHT ADMINISTRATION")
    with pytest.raises(ValidationError):
        normalize_category("   ")
