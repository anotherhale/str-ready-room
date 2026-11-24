"""Identity provider and authorization policy tests."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.authorization.policy_authorizer import PolicyAuthorizer
from app.adapters.identity.single_user_provider import SingleUserAuthProvider
from app.api.error_handlers import register_error_handlers
from app.application.commands import CreateTaskCommand, ListTasksQuery
from app.domain.authorization.permissions import OPERATOR_PERMISSIONS, Permission
from app.domain.identity.identity import RequestContext
from app.domain.identity.principal import Principal
from app.domain.shared.errors import AuthenticationError, AuthorizationError
from tests.doubles import MembershipState


class _FakeSettings:
    operator_id = "maverick"
    operator_display_name = "Maverick"
    default_timezone = "America/New_York"


def _provider() -> SingleUserAuthProvider:
    return SingleUserAuthProvider(
        user_id=_FakeSettings.operator_id,
        display_name=_FakeSettings.operator_display_name,
        timezone=_FakeSettings.default_timezone,
    )


def test_single_user_provider_resolves_configured_operator():
    provider = _provider()
    principal = provider.resolve_current_principal(RequestContext())
    assert principal.id == "maverick"
    assert principal.display_name == "Maverick"
    assert principal.timezone == "America/New_York"


def test_single_user_provider_ignores_credentials():
    # No login: even with no headers/context, the demo operator is returned.
    provider = _provider()
    principal = provider.resolve_current_principal(RequestContext(headers=()))
    assert principal.id == "maverick"


def test_policy_authorizer_allows_operator_all_permissions():
    authorizer = PolicyAuthorizer()
    principal = Principal(id="maverick", display_name="Maverick", timezone="UTC", roles=frozenset({"operator"}))
    for permission in OPERATOR_PERMISSIONS:
        decision = authorizer.authorize(principal, permission)
        assert decision.allowed, permission


def test_policy_authorizer_denies_viewer_mutations():
    authorizer = PolicyAuthorizer()
    viewer = Principal(id="obs", display_name="Observer", timezone="UTC", roles=frozenset({"viewer"}))
    assert authorizer.authorize(viewer, Permission.TASKS_READ).allowed
    assert not authorizer.authorize(viewer, Permission.TASKS_DELETE).allowed
    assert not authorizer.authorize(viewer, Permission.DEMO_RESET).allowed


def test_deny_decision_has_code_and_reason():
    authorizer = PolicyAuthorizer()
    viewer = Principal(id="obs", display_name="Observer", timezone="UTC", roles=frozenset({"viewer"}))
    decision = authorizer.authorize(viewer, Permission.DEMO_RESET)
    assert decision.allowed is False
    assert decision.code
    assert decision.reason


# -- multi-principal harness (issue #14 / P0-12) ---------------------------
#
# These tests prove the harness itself works: it resolves distinct principals in
# one test, refuses inactive memberships, and drives the real services and the
# real error mapping.  Feature tests build on these fixtures (P1-19, P2-15).


def test_roster_covers_the_required_squadron_shapes(squadron_roster):
    assert len(squadron_roster) == 5
    roles = {member.role for member in squadron_roster.values()}
    assert {"squadron_admin", "member", "team_lead", "read_only"} <= roles
    assert sum(1 for m in squadron_roster.values() if not m.is_active) == 1


def test_harness_resolves_two_distinct_principals_in_one_test(test_auth_provider):
    maverick = test_auth_provider.select("maverick")
    viper = test_auth_provider.select("viper")

    assert maverick.id == "maverick"
    assert viper.id == "viper"
    assert maverick.id != viper.id
    assert maverick.roles != viper.roles


def test_harness_selects_a_principal_per_request_by_header(test_auth_provider):
    from tests.doubles import TestAuthProvider as _Provider

    as_iceman = test_auth_provider.resolve_current_principal(
        RequestContext(headers=((_Provider.HEADER, "iceman"),))
    )
    as_goose = test_auth_provider.resolve_current_principal(
        RequestContext(headers=((_Provider.HEADER, "goose"),))
    )

    assert as_iceman.id == "iceman"
    assert as_goose.id == "goose"
    assert "read_only" in as_iceman.roles


def test_unselected_provider_rejects_the_request(test_auth_provider):
    with pytest.raises(AuthenticationError) as excinfo:
        test_auth_provider.resolve_current_principal(RequestContext())

    assert excinfo.value.code == "unauthenticated"


def test_suspended_membership_has_no_usable_identity(squadron_roster):
    slider = squadron_roster["slider"]

    assert slider.membership_state is MembershipState.SUSPENDED
    with pytest.raises(AuthenticationError):
        slider.principal()


def test_authentication_error_maps_to_401_not_403():
    app = FastAPI()

    @app.get("/whoami")
    def _whoami() -> dict:  # pragma: no cover - always raises
        raise AuthenticationError("no identity")

    @app.get("/may-i")
    def _may_i() -> dict:  # pragma: no cover - always raises
        raise AuthorizationError("not allowed")

    register_error_handlers(app)
    with TestClient(app) as client:
        unauthenticated = client.get("/whoami")
        forbidden = client.get("/may-i")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "unauthenticated"
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"


def test_read_only_member_is_denied_a_mutation_the_admin_can_perform(test_container, squadron_roster):
    authorizer = test_container.authorizer
    admin = squadron_roster["maverick"].principal()
    reader = squadron_roster["iceman"].principal()

    assert authorizer.authorize(admin, Permission.TASKS_CREATE).allowed
    assert not authorizer.authorize(reader, Permission.TASKS_CREATE).allowed


def test_two_principals_get_isolated_task_lists(test_container):
    provider = test_container.auth_provider
    tasks = test_container.tasks

    maverick = provider.select("maverick")
    created = tasks.create_task(maverick, CreateTaskCommand(title="Squadron CC call", category="Duty"))

    assert [t.id for t in tasks.list_tasks(maverick, ListTasksQuery())] == [created.id]

    # ``iceman`` holds tasks:read, so an empty list proves ownership filtering
    # rather than a permission denial hiding the leak.
    iceman = provider.select("iceman")
    assert tasks.list_tasks(iceman, ListTasksQuery()) == []


def test_team_lead_has_no_demo_grant_until_adr_004_lands(test_container, squadron_roster):
    # DECISIONS C-007: the harness must not pre-authorize the ADR-004 matrix.
    goose = squadron_roster["goose"].principal()

    assert "operator" not in goose.roles
    assert not test_container.authorizer.authorize(goose, Permission.DEMO_RESET).allowed
