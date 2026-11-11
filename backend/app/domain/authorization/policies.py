"""Policy concepts: a role-to-permission mapping plus resource rules."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..identity.principal import Principal
from .permissions import OPERATOR_PERMISSIONS, VIEWER_PERMISSIONS, Permission


@dataclass(frozen=True)
class RoleGrant:
    """A named set of permissions."""

    role: str
    permissions: frozenset[Permission]


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
    """The demo policy: the configured operator receives every permission."""
    return Policy(
        name="single-operator-demo",
        grants=(
            RoleGrant(role="operator", permissions=OPERATOR_PERMISSIONS),
            RoleGrant(role="viewer", permissions=VIEWER_PERMISSIONS),
        ),
    )
