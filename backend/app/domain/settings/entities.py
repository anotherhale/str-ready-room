"""Operator settings and categories.

Typed models so that no unvalidated string leaks into business logic.  The
warning window is validated against the bounds defined by the urgency module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from ..shared.errors import ValidationError
from ..tasks.urgency import DEFAULT_WARNING_WINDOW, validate_warning_window
from ..tasks.value_objects import category_key, normalize_category

DEFAULT_TIMEZONE = "America/Denver"

#: Initial category assumptions (operator-editable, not validated requirements).
DEFAULT_CATEGORIES: tuple[str, ...] = (
    "Flight Administration",
    "Maintenance",
    "Detachment Operations",
    "Personnel",
    "Logistics",
    "General",
)

#: Marker recording which seed generation last ran.
CURRENT_SEED_VERSION = 1

#: Markers for the *optional* integration seeds.  They live beside the core
#: ``seed_version`` so every seeder has its own idempotency marker and the
#: integrations can be seeded (or not) independently (see DECISIONS D-028).
CURRENT_CALENDAR_SEED_VERSION = 1
CURRENT_EMAIL_SEED_VERSION = 1


def validate_timezone(name: str) -> str:
    if not name or not isinstance(name, str):
        raise ValidationError("Timezone is required")
    try:
        ZoneInfo(name)
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"Unknown timezone: {name!r}") from exc
    return name


@dataclass
class OperatorSettings:
    """Per-operator settings.  One row per owner in the demo."""

    owner_id: str
    warning_window_days: int = DEFAULT_WARNING_WINDOW
    timezone: str = DEFAULT_TIMEZONE
    seed_version: int = 0
    calendar_seed_version: int = 0
    email_seed_version: int = 0
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.warning_window_days = validate_warning_window(self.warning_window_days)
        self.timezone = validate_timezone(self.timezone)

    def update(
        self,
        now: datetime,
        *,
        warning_window_days: int | None = None,
        timezone: str | None = None,
    ) -> None:
        if warning_window_days is not None:
            self.warning_window_days = validate_warning_window(warning_window_days)
        if timezone is not None:
            self.timezone = validate_timezone(timezone)
        self.updated_at = now


@dataclass
class Category:
    """A configurable task category."""

    id: str
    owner_id: str
    name: str
    created_at: datetime | None = None
    active: bool = True
    is_default: bool = False

    def __post_init__(self) -> None:
        self.name = normalize_category(self.name)

    @property
    def key(self) -> str:
        return category_key(self.name)

    def rename(self, name: str) -> None:
        self.name = normalize_category(name)

    def deactivate(self) -> None:
        self.active = False
