"""Authorization decision tests (pure domain)."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.authorization.authorization_service import (
    AuthorizationContext,
    AuthorizationPolicyService,
)
from app.domain.authorization.permissions import Permission
from app.domain.authorization.policies import default_policy
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
