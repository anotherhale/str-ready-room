"""Squadron and membership enumerations."""

from __future__ import annotations

from enum import Enum


class MembershipStatus(str, Enum):
    """The single state of a membership (ADR-003 §4).

    Only ``ACTIVE`` authorizes work.  ``INVITED`` is not a weak ``ACTIVE``:
    an invited person holds no role in any decision.
    """

    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class SquadronRole(str, Enum):
    """Production squadron roles (ADR-004).

    Demo-only aliases (``operator``/``viewer``) live in the demo policy and are
    never membership roles.
    """

    SQUADRON_ADMIN = "squadron_admin"
    OFFICER = "officer"
    TEAM_LEAD = "team_lead"
    MEMBER = "member"
    READ_ONLY = "read_only"
