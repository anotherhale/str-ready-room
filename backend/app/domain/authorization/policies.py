"""Policy concepts: a role-to-permission mapping plus resource rules."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..identity.principal import Principal
from .permissions import (
    ALL_PERMISSIONS,
    OPERATOR_PERMISSIONS,
    READ_ONLY_PERMISSIONS,
    VIEWER_PERMISSIONS,
    Permission,
)


@dataclass(frozen=True)
class RoleGrant:
    """A named set of permissions."""

    role: str
    permissions: frozenset[Permission]


#: Permissions only the squadron administrator holds (ADR-004 §3).
_ADMIN_ONLY: frozenset[Permission] = frozenset(
    {
        Permission.TASKS_DELETE,
        Permission.SQUADRON_MANAGE,
        Permission.MEMBERS_INVITE,
        Permission.MEMBERS_MANAGE,
        Permission.TEAMS_MANAGE,
        Permission.DUTY_POSITIONS_MANAGE,
        Permission.SETTINGS_UPDATE,
        Permission.CATEGORIES_MANAGE,
        Permission.AUDIT_READ,
        Permission.WORKFLOWS_MANAGE,
        Permission.AGENTS_MANAGE,
    }
)

#: Operational permissions the officer holds and the team lead does not: the
#: team lead is ceilinged at team scope, so squadron-wide agent authority and
#: squadron-wide calendar writes are out (ADR-004 §3, §5).
_OFFICER_ONLY: frozenset[Permission] = frozenset(
    {
        Permission.CALENDAR_WRITE,
        Permission.AGENTS_READ,
        Permission.DELEGATIONS_READ,
        Permission.DELEGATIONS_GRANT,
        Permission.DELEGATIONS_REVOKE,
    }
)

#: What a member may do beyond reading: participate in their own and their
#: team's work.  No assignment, no deletion, no recurrence rule change.
_MEMBER_WRITE: frozenset[Permission] = frozenset(
    {
        Permission.TASKS_CREATE,
        Permission.TASKS_UPDATE,
        Permission.TASKS_COMPLETE,
        Permission.TASKS_REOPEN,
        Permission.TASKS_SHARE,
        Permission.TASKS_COMMENT,
        Permission.TASKS_ACKNOWLEDGE,
        Permission.TASKS_HANDOFF,
        Permission.RECURRENCE_OVERRIDE,
        Permission.EMAIL_CAPTURE,
        Permission.TURNOVER_ACKNOWLEDGE,
        Permission.NOTES_WRITE,
        Permission.NOTES_SHARE,
    }
)

SQUADRON_ADMIN_PERMISSIONS: frozenset[Permission] = ALL_PERMISSIONS - {
    Permission.DEMO_RESET,
    Permission.DEMO_SIMULATE,
}
OFFICER_PERMISSIONS: frozenset[Permission] = SQUADRON_ADMIN_PERMISSIONS - _ADMIN_ONLY
TEAM_LEAD_PERMISSIONS: frozenset[Permission] = OFFICER_PERMISSIONS - _OFFICER_ONLY
MEMBER_PERMISSIONS: frozenset[Permission] = READ_ONLY_PERMISSIONS | _MEMBER_WRITE
READ_ONLY_ROLE_PERMISSIONS: frozenset[Permission] = READ_ONLY_PERMISSIONS

#: The five roles of ADR-004 §1.  Effective permissions are the union of a
#: principal's grants; the narrowest scope ceiling still governs each grant.
ROLE_GRANTS: dict[str, frozenset[Permission]] = {
    "squadron_admin": SQUADRON_ADMIN_PERMISSIONS,
    "officer": OFFICER_PERMISSIONS,
    "team_lead": TEAM_LEAD_PERMISSIONS,
    "member": MEMBER_PERMISSIONS,
    "read_only": READ_ONLY_ROLE_PERMISSIONS,
}


@dataclass(frozen=True)
class OwnershipRule:
    """Describes how a resource is owned for authorization purposes."""

    owner_attribute: str = "owner_id"


@dataclass(frozen=True)
class Policy:
    """A collection of role grants used to compute a principal's permissions."""

    name: str
    grants: tuple[RoleGrant, ...] = ()
    ownership: OwnershipRule = field(default_factory=OwnershipRule)

    def permissions_for(self, principal: Principal) -> frozenset[Permission]:
        granted: set[Permission] = set()
        for grant in self.grants:
            if grant.role in principal.roles:
                granted |= grant.permissions
        return frozenset(granted)


def default_policy() -> Policy:
    """The demo policy: the configured operator receives every permission.

    Only this policy wires the `operator`/`viewer` aliases; the squadron roles
    are granted here too so one grant table serves every consumer.
    """
    return Policy(
        name="single-operator-demo",
        grants=(
            RoleGrant(role="operator", permissions=OPERATOR_PERMISSIONS),
            RoleGrant(role="viewer", permissions=VIEWER_PERMISSIONS),
            *(
                RoleGrant(role=role, permissions=permissions)
                for role, permissions in ROLE_GRANTS.items()
            ),
        ),
    )
