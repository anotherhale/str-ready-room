"""Authorization decision tests (pure domain)."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.authorization.authorization_service import (
    AuthorizationContext,
    AuthorizationPolicyService,
)
from app.domain.authorization.permissions import (
    OPERATOR_PERMISSIONS,
    VIEWER_PERMISSIONS,
    Permission,
)
from app.domain.authorization.policies import ROLE_GRANTS, default_policy
from app.domain.identity.principal import Principal

OPERATOR = Principal(id="op-1", display_name="Maverick", timezone="America/New_York", roles=frozenset({"operator"}))
VIEWER = Principal(id="op-2", display_name="Observer", timezone="America/New_York", roles=frozenset({"viewer"}))
NOBODY = Principal(id="op-3", display_name="Nobody", timezone="America/New_York", roles=frozenset())


@dataclass
class Resource:
    owner_id: str


def service() -> AuthorizationPolicyService:
    return AuthorizationPolicyService(default_policy())


def test_operator_is_allowed_every_permission():
    svc = service()
    for permission in Permission:
        assert svc.decide(OPERATOR, permission).allowed is True


def test_viewer_cannot_write():
    svc = service()
    assert svc.decide(VIEWER, Permission.TASKS_READ).allowed is True
    decision = svc.decide(VIEWER, Permission.TASKS_DELETE)
    assert decision.allowed is False
    assert decision.code == "forbidden"


def test_principal_without_roles_is_denied():
    assert service().decide(NOBODY, Permission.TASKS_READ).allowed is False


def test_ownership_denial_is_distinct_code():
    svc = service()
    resource = Resource(owner_id="someone-else")
    decision = svc.decide(OPERATOR, Permission.TASKS_UPDATE, resource=resource)
    assert decision.allowed is False
    assert decision.code == "forbidden_ownership"


def test_ownership_allow_when_owner_matches():
    svc = service()
    resource = Resource(owner_id=OPERATOR.id)
    assert svc.decide(OPERATOR, Permission.TASKS_UPDATE, resource=resource).allowed is True


def test_context_owner_overrides_resource():
    svc = service()
    decision = svc.decide(
        OPERATOR,
        Permission.TASKS_UPDATE,
        resource=Resource(owner_id=OPERATOR.id),
        context=AuthorizationContext(owner_id="other"),
    )
    assert decision.allowed is False


def test_permission_check_precedes_ownership():
    svc = service()
    decision = svc.decide(NOBODY, Permission.TASKS_DELETE, resource=Resource(owner_id=NOBODY.id))
    assert decision.allowed is False
    assert decision.code == "forbidden"


# --- ADR-004 role grants (P1-03) -------------------------------------------

ROLES = ("squadron_admin", "officer", "team_lead", "member", "read_only")

#: ADR-004 §3 matrix, restricted to the 34 permissions P1-03 added.  Each entry
#: is the exact set of roles that grant the permission.
NEW_PERMISSION_GRANTS = {
    Permission.TASKS_ASSIGN: {"squadron_admin", "officer", "team_lead"},
    Permission.TASKS_SHARE: {"squadron_admin", "officer", "team_lead", "member"},
    Permission.TASKS_COMMENT: {"squadron_admin", "officer", "team_lead", "member"},
    Permission.TASKS_ACKNOWLEDGE: {"squadron_admin", "officer", "team_lead", "member"},
    Permission.TASKS_HANDOFF: {"squadron_admin", "officer", "team_lead", "member"},
    Permission.BRIEFING_WRITE: {"squadron_admin", "officer", "team_lead"},
    Permission.RECURRENCE_OVERRIDE: {"squadron_admin", "officer", "team_lead", "member"},
    Permission.SQUADRON_READ: set(ROLES),
    Permission.SQUADRON_MANAGE: {"squadron_admin"},
    Permission.MEMBERS_READ: set(ROLES),
    Permission.MEMBERS_INVITE: {"squadron_admin"},
    Permission.MEMBERS_MANAGE: {"squadron_admin"},
    Permission.TEAMS_READ: set(ROLES),
    Permission.TEAMS_MANAGE: {"squadron_admin"},
    Permission.DUTY_POSITIONS_READ: set(ROLES),
    Permission.DUTY_POSITIONS_MANAGE: {"squadron_admin"},
    Permission.NOTIFICATIONS_READ: set(ROLES),
    Permission.NOTIFICATIONS_SEND: {"squadron_admin", "officer", "team_lead"},
    Permission.TURNOVER_READ: set(ROLES),
    Permission.TURNOVER_BUILD: {"squadron_admin", "officer", "team_lead"},
    Permission.TURNOVER_ACKNOWLEDGE: {"squadron_admin", "officer", "team_lead", "member"},
    Permission.NOTES_READ: set(ROLES),
    Permission.NOTES_WRITE: {"squadron_admin", "officer", "team_lead", "member"},
    Permission.NOTES_SHARE: {"squadron_admin", "officer", "team_lead", "member"},
    Permission.AUDIT_READ: {"squadron_admin"},
    Permission.APPROVALS_READ: set(ROLES),
    Permission.APPROVALS_DECIDE: {"squadron_admin", "officer", "team_lead"},
    Permission.WORKFLOWS_READ: set(ROLES),
    Permission.WORKFLOWS_MANAGE: {"squadron_admin"},
    Permission.AGENTS_READ: {"squadron_admin", "officer"},
    Permission.AGENTS_MANAGE: {"squadron_admin"},
    Permission.DELEGATIONS_READ: {"squadron_admin", "officer"},
    Permission.DELEGATIONS_GRANT: {"squadron_admin", "officer"},
    Permission.DELEGATIONS_REVOKE: {"squadron_admin", "officer"},
}

#: Authority over the squadron boundary itself (ADR-004 §3).
ADMINISTRATION = {
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
    Permission.DEMO_RESET,
    Permission.DEMO_SIMULATE,
}


def test_catalog_has_the_fifty_four_adr_permissions():
    assert len(Permission) == 54


def test_every_adr_role_has_an_explicit_grant():
    assert set(ROLE_GRANTS) == set(ROLES)
    for role in ROLES:
        assert ROLE_GRANTS[role], role


def test_new_permissions_are_granted_to_exactly_the_adr_roles():
    for permission, expected in NEW_PERMISSION_GRANTS.items():
        actual = {role for role in ROLES if permission in ROLE_GRANTS[role]}
        assert actual == expected, f"{permission.value}: expected {expected}, got {actual}"


def test_read_only_role_mutates_nothing():
    mutating = {
        permission
        for permission in Permission
        if not permission.value.endswith(":read") and permission is not Permission.DASHBOARD_READ
    }
    assert ROLE_GRANTS["read_only"].isdisjoint(mutating)


def test_team_lead_has_no_squadron_administration():
    assert ROLE_GRANTS["team_lead"].isdisjoint(ADMINISTRATION)
    assert not any(permission.value.endswith(":manage") for permission in ROLE_GRANTS["team_lead"])


def test_only_the_admin_roles_hold_the_administration_set():
    for permission in ADMINISTRATION | {Permission.DELEGATIONS_GRANT, Permission.DELEGATIONS_REVOKE}:
        holders = {role for role in ROLES if permission in ROLE_GRANTS[role]}
        assert holders <= {"squadron_admin", "officer"}, permission.value
    for permission in {Permission.AGENTS_READ, Permission.DELEGATIONS_READ}:
        holders = {role for role in ROLES if permission in ROLE_GRANTS[role]}
        assert holders == {"squadron_admin", "officer"}, permission.value


def test_member_cannot_assign_delete_or_change_a_recurrence_rule():
    for permission in (
        Permission.TASKS_ASSIGN,
        Permission.TASKS_DELETE,
        Permission.RECURRENCE_WRITE,
        Permission.BRIEFING_WRITE,
    ):
        assert permission not in ROLE_GRANTS["member"]


def test_no_production_role_holds_a_demo_permission():
    for role in ROLES:
        assert ROLE_GRANTS[role].isdisjoint({Permission.DEMO_RESET, Permission.DEMO_SIMULATE})


def test_demo_aliases_stay_compatible():
    assert ROLE_GRANTS["read_only"] == VIEWER_PERMISSIONS
    assert VIEWER_PERMISSIONS.issubset(OPERATOR_PERMISSIONS)
    assert Permission.DEMO_SIMULATE in OPERATOR_PERMISSIONS
    assert Permission.DEMO_SIMULATE not in VIEWER_PERMISSIONS


def test_squadron_role_principals_are_decided_by_their_grants():
    svc = service()
    member = Principal(
        id="m-1", display_name="Member", timezone="America/Denver", roles=frozenset({"member"})
    )
    assert svc.decide(member, Permission.TASKS_COMPLETE).allowed is True
    assert svc.decide(member, Permission.TASKS_ASSIGN).allowed is False
    lead = Principal(
        id="t-1", display_name="Lead", timezone="America/Denver", roles=frozenset({"team_lead"})
    )
    assert svc.decide(lead, Permission.TASKS_ASSIGN).allowed is True
    assert svc.decide(lead, Permission.MEMBERS_MANAGE).allowed is False
