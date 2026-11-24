"""Squadron aggregate and membership lifecycle.

ADR-003 fixes one squadron per installation and a membership state machine with
four states.  These are plain dataclasses: no framework, ORM, or transport
schema is imported, so the transitions are testable without a database.

Legal transitions (ADR-003 §4)::

    -            -> INVITED     invite()
    INVITED      -> ACTIVE      accept()
    INVITED      -> REMOVED     revoke_invitation()
    ACTIVE       -> SUSPENDED   suspend()
    SUSPENDED    -> ACTIVE      reinstate()
    ACTIVE       -> REMOVED     remove()
    SUSPENDED    -> REMOVED     remove()
    REMOVED      -> INVITED     reinvite()   (then accept())

Everything else, including a repeated transition, is a conflict.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from ..shared.errors import ConflictError, ValidationError
from .enums import MembershipStatus, SquadronRole

INVALID_TRANSITION = "invalid_membership_transition"
LAST_ADMINISTRATOR = "last_administrator"


def _normalize_squadron_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValidationError("Squadron name is required")
    if len(cleaned) > 200:
        raise ValidationError("Squadron name must be 200 characters or fewer")
    return cleaned


@dataclass
class Squadron:
    """The single squadron that scopes every record (ADR-003 §1)."""

    id: str
    name: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, *, id: str, name: str, now: datetime) -> Squadron:
        if not id:
            raise ValidationError("Squadron id is required")
        return cls(
            id=id,
            name=_normalize_squadron_name(name),
            created_at=now,
            updated_at=now,
        )

    def rename(self, name: str, now: datetime) -> None:
        cleaned = _normalize_squadron_name(name)
        if cleaned == self.name:
            return
        self.name = cleaned
        self.updated_at = now


@dataclass
class Membership:
    """One person's standing in the squadron.

    ``status`` is the authority; the timestamps record history and are never
    used to derive access on their own.
    """

    id: str
    squadron_id: str
    user_id: str
    role: SquadronRole
    status: MembershipStatus
    created_at: datetime
    updated_at: datetime
    invited_by: str | None = None
    invited_at: datetime | None = None
    activated_at: datetime | None = None
    suspended_at: datetime | None = None
    removed_at: datetime | None = None

    # -- construction --------------------------------------------------
    @classmethod
    def invite(
        cls,
        *,
        id: str,
        squadron_id: str,
        user_id: str,
        role: SquadronRole,
        invited_by: str,
        now: datetime,
    ) -> Membership:
        if not id:
            raise ValidationError("Membership id is required")
        if not squadron_id:
            raise ValidationError("Membership squadron id is required")
        if not user_id:
            raise ValidationError("Membership user id is required")
        if not invited_by:
            raise ValidationError("Invitation must name the inviting administrator")
        return cls(
            id=id,
            squadron_id=squadron_id,
            user_id=user_id,
            role=role,
            status=MembershipStatus.INVITED,
            created_at=now,
            updated_at=now,
            invited_by=invited_by,
            invited_at=now,
        )

    # -- derived state -------------------------------------------------
    @property
    def is_active(self) -> bool:
        """Only an active membership authorizes work (ADR-003 §5)."""
        return self.status is MembershipStatus.ACTIVE

    @property
    def is_invited(self) -> bool:
        return self.status is MembershipStatus.INVITED

    @property
    def is_removed(self) -> bool:
        return self.status is MembershipStatus.REMOVED

    @property
    def is_squadron_admin(self) -> bool:
        return self.role is SquadronRole.SQUADRON_ADMIN

    # -- transitions ---------------------------------------------------
    def accept(self, now: datetime) -> None:
        """INVITED -> ACTIVE.  The invitee joins with the invited role."""
        self._require(MembershipStatus.INVITED, action="accept")
        self.status = MembershipStatus.ACTIVE
        self.activated_at = now
        self.updated_at = now

    def revoke_invitation(self, now: datetime) -> None:
        """INVITED -> REMOVED.  The row is retained for audit."""
        self._require(MembershipStatus.INVITED, action="revoke an invitation")
        self._mark_removed(now)

    def suspend(self, now: datetime) -> None:
        """ACTIVE -> SUSPENDED.  Owned work is retained, never reassigned."""
        self._require(MembershipStatus.ACTIVE, action="suspend")
        self.status = MembershipStatus.SUSPENDED
        self.suspended_at = now
        self.updated_at = now

    def reinstate(self, now: datetime) -> None:
        """SUSPENDED -> ACTIVE.  Shares and duty authority come back."""
        self._require(MembershipStatus.SUSPENDED, action="reinstate")
        self.status = MembershipStatus.ACTIVE
        self.activated_at = now
        self.suspended_at = None
        self.updated_at = now

    def remove(self, now: datetime) -> None:
        """ACTIVE|SUSPENDED -> REMOVED.  Terminal for access, not for data."""
        self._require(
            MembershipStatus.ACTIVE,
            MembershipStatus.SUSPENDED,
            action="remove",
        )
        self._mark_removed(now)

    def reinvite(self, *, role: SquadronRole, invited_by: str, now: datetime) -> None:
        """REMOVED -> INVITED.  Re-entry is always an explicit new invitation."""
        self._require(MembershipStatus.REMOVED, action="re-invite")
        if not invited_by:
            raise ValidationError("Invitation must name the inviting administrator")
        self.role = role
        self.status = MembershipStatus.INVITED
        self.invited_by = invited_by
        self.invited_at = now
        self.updated_at = now

    def change_role(self, role: SquadronRole, now: datetime) -> None:
        """Role changes are membership updates, not transitions (ADR-003 §4)."""
        if self.status is MembershipStatus.REMOVED:
            raise ConflictError(
                "A removed membership has no role to change; re-invite instead",
                code=INVALID_TRANSITION,
            )
        if role is self.role:
            return
        self.role = role
        self.updated_at = now

    # -- internals -----------------------------------------------------
    def _mark_removed(self, now: datetime) -> None:
        self.status = MembershipStatus.REMOVED
        self.removed_at = now
        self.updated_at = now

    def _require(self, *allowed: MembershipStatus, action: str) -> None:
        if self.status in allowed:
            return
        raise ConflictError(
            f"Cannot {action} a membership in state '{self.status.value}'",
            code=INVALID_TRANSITION,
        )


def ensure_not_last_administrator(memberships: Iterable[Membership], *, losing_user_id: str) -> None:
    """Reject a change that would leave no active squadron administrator.

    Suspension, removal, or demotion of the last active ``squadron_admin`` would
    lock the installation out; recovery is an operator procedure, not a route.
    """
    remaining = [
        membership
        for membership in memberships
        if membership.user_id != losing_user_id and membership.is_active and membership.is_squadron_admin
    ]
    if not remaining:
        raise ConflictError(
            "The squadron must keep at least one active administrator",
            code=LAST_ADMINISTRATOR,
        )
