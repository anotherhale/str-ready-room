"""Squadron aggregate and membership lifecycle tests (pure domain, no database)."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.shared.errors import ConflictError, ValidationError
from app.domain.squadron import (
    INVALID_TRANSITION,
    LAST_ADMINISTRATOR,
    Membership,
    MembershipStatus,
    Squadron,
    SquadronRole,
    ensure_not_last_administrator,
)

NOW = datetime(2026, 3, 10, 9, 0, 0)
LATER = datetime(2026, 3, 10, 17, 0, 0)


def make_membership(**overrides) -> Membership:
    base = {
        "id": "m1",
        "squadron_id": "sq-1",
        "user_id": "u1",
        "role": SquadronRole.MEMBER,
        "invited_by": "admin-1",
        "now": NOW,
    }
    base.update(overrides)
    return Membership.invite(**base)


def make_active(**overrides) -> Membership:
    membership = make_membership(**overrides)
    membership.accept(LATER)
    return membership


def test_squadron_create_normalizes_name_and_sets_timestamps():
    squadron = Squadron.create(id="sq-1", name="  1st   Detachment ", now=NOW)
    assert squadron.name == "1st Detachment"
    assert squadron.created_at == NOW
    assert squadron.updated_at == NOW


def test_squadron_requires_id_and_name():
    with pytest.raises(ValidationError):
        Squadron.create(id="", name="Squadron", now=NOW)
    with pytest.raises(ValidationError):
        Squadron.create(id="sq-1", name="   ", now=NOW)


def test_squadron_rename_is_noop_when_unchanged():
    squadron = Squadron.create(id="sq-1", name="Squadron", now=NOW)
    squadron.rename("Squadron", LATER)
    assert squadron.updated_at == NOW


def test_invite_starts_invited_and_holds_no_authority():
    membership = make_membership()
    assert membership.status is MembershipStatus.INVITED
    assert membership.is_invited
    assert not membership.is_active
    assert membership.invited_by == "admin-1"
    assert membership.invited_at == NOW


def test_invite_requires_an_inviting_administrator():
    with pytest.raises(ValidationError):
        make_membership(invited_by="")


def test_accept_moves_invited_to_active():
    membership = make_membership()
    membership.accept(LATER)
    assert membership.status is MembershipStatus.ACTIVE
    assert membership.is_active
    assert membership.activated_at == LATER
    assert membership.updated_at == LATER


def test_accept_is_not_repeatable():
    membership = make_active()
    with pytest.raises(ConflictError) as exc:
        membership.accept(LATER)
    assert exc.value.code == INVALID_TRANSITION


def test_revoke_invitation_removes_an_invited_membership():
    membership = make_membership()
    membership.revoke_invitation(LATER)
    assert membership.status is MembershipStatus.REMOVED
    assert membership.is_removed
    assert not membership.is_active
    assert membership.removed_at == LATER


def test_revoke_requires_an_invited_membership():
    membership = make_active()
    with pytest.raises(ConflictError) as exc:
        membership.revoke_invitation(LATER)
    assert exc.value.code == INVALID_TRANSITION


def test_suspend_moves_active_to_suspended_without_losing_role():
    membership = make_active()
    membership.suspend(LATER)
    assert membership.status is MembershipStatus.SUSPENDED
    assert not membership.is_active
    assert membership.role is SquadronRole.MEMBER
    assert membership.suspended_at == LATER


def test_suspend_requires_active():
    membership = make_membership()
    with pytest.raises(ConflictError) as exc:
        membership.suspend(LATER)
    assert exc.value.code == INVALID_TRANSITION


def test_suspend_is_not_repeatable():
    membership = make_active()
    membership.suspend(LATER)
    with pytest.raises(ConflictError):
        membership.suspend(LATER)


def test_reinstate_moves_suspended_to_active():
    membership = make_active()
    membership.suspend(LATER)
    membership.reinstate(LATER)
    assert membership.status is MembershipStatus.ACTIVE
    assert membership.is_active
    assert membership.suspended_at is None


def test_reinstate_requires_suspended():
    membership = make_active()
    with pytest.raises(ConflictError) as exc:
        membership.reinstate(LATER)
    assert exc.value.code == INVALID_TRANSITION


def test_remove_from_active_is_terminal_for_access():
    membership = make_active()
    membership.remove(LATER)
    assert membership.status is MembershipStatus.REMOVED
    assert not membership.is_active
    assert membership.removed_at == LATER


def test_remove_from_suspended_is_allowed():
    membership = make_active()
    membership.suspend(LATER)
    membership.remove(LATER)
    assert membership.status is MembershipStatus.REMOVED


def test_remove_requires_active_or_suspended():
    membership = make_membership()
    with pytest.raises(ConflictError) as exc:
        membership.remove(LATER)
    assert exc.value.code == INVALID_TRANSITION


def test_remove_is_not_repeatable():
    membership = make_active()
    membership.remove(LATER)
    with pytest.raises(ConflictError):
        membership.remove(LATER)


def test_removed_membership_returns_only_through_a_new_invitation():
    membership = make_active()
    membership.remove(LATER)
    membership.reinvite(role=SquadronRole.OFFICER, invited_by="admin-2", now=LATER)
    assert membership.status is MembershipStatus.INVITED
    assert membership.role is SquadronRole.OFFICER
    assert membership.invited_by == "admin-2"
    assert not membership.is_active
    membership.accept(LATER)
    assert membership.is_active
    assert membership.role is SquadronRole.OFFICER


def test_reinvite_requires_removed():
    membership = make_active()
    with pytest.raises(ConflictError) as exc:
        membership.reinvite(role=SquadronRole.MEMBER, invited_by="admin-1", now=LATER)
    assert exc.value.code == INVALID_TRANSITION


def test_change_role_updates_an_active_membership():
    membership = make_active()
    membership.change_role(SquadronRole.TEAM_LEAD, LATER)
    assert membership.role is SquadronRole.TEAM_LEAD
    assert membership.updated_at == LATER


def test_change_role_is_a_noop_for_the_same_role():
    membership = make_active()
    membership.change_role(SquadronRole.MEMBER, LATER)
    assert membership.updated_at == LATER


def test_change_role_rejects_a_removed_membership():
    membership = make_active()
    membership.remove(LATER)
    with pytest.raises(ConflictError) as exc:
        membership.change_role(SquadronRole.OFFICER, LATER)
    assert exc.value.code == INVALID_TRANSITION


def test_last_administrator_guard_blocks_losing_the_only_admin():
    admin = make_active(id="m1", user_id="admin-1", role=SquadronRole.SQUADRON_ADMIN)
    member = make_active(id="m2", user_id="u2", role=SquadronRole.MEMBER)
    with pytest.raises(ConflictError) as exc:
        ensure_not_last_administrator([admin, member], losing_user_id="admin-1")
    assert exc.value.code == LAST_ADMINISTRATOR


def test_last_administrator_guard_allows_a_change_when_another_admin_remains():
    first = make_active(id="m1", user_id="admin-1", role=SquadronRole.SQUADRON_ADMIN)
    second = make_active(id="m2", user_id="admin-2", role=SquadronRole.SQUADRON_ADMIN)
    ensure_not_last_administrator([first, second], losing_user_id="admin-1")


def test_last_administrator_guard_ignores_inactive_administrators():
    admin = make_active(id="m1", user_id="admin-1", role=SquadronRole.SQUADRON_ADMIN)
    suspended = make_active(id="m2", user_id="admin-2", role=SquadronRole.SQUADRON_ADMIN)
    suspended.suspend(LATER)
    with pytest.raises(ConflictError) as exc:
        ensure_not_last_administrator([admin, suspended], losing_user_id="admin-1")
    assert exc.value.code == LAST_ADMINISTRATOR
