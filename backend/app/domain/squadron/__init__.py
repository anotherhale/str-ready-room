"""Squadron aggregate: one squadron per installation and membership lifecycle."""

from .entities import (
    INVALID_TRANSITION,
    LAST_ADMINISTRATOR,
    Membership,
    Squadron,
    ensure_not_last_administrator,
)
from .enums import MembershipStatus, SquadronRole

__all__ = [
    "INVALID_TRANSITION",
    "LAST_ADMINISTRATOR",
    "Membership",
    "MembershipStatus",
    "Squadron",
    "SquadronRole",
    "ensure_not_last_administrator",
]
