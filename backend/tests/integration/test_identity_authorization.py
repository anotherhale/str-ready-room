"""Identity provider and authorization policy tests."""
from __future__ import annotations

from app.adapters.authorization.policy_authorizer import PolicyAuthorizer
from app.adapters.identity.single_user_provider import SingleUserAuthProvider
from app.domain.authorization.permissions import OPERATOR_PERMISSIONS, Permission
from app.domain.identity.identity import RequestContext
from app.domain.identity.principal import Principal


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
