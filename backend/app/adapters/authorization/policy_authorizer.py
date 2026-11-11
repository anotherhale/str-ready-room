"""Authorization adapter: wraps the pure policy service behind the port.

The same ``authorize`` call path is used by the demo policy and by any future
policy engine; nothing in the services branches on "demo mode".
"""
from __future__ import annotations

from ...domain.authorization.authorization_service import (
    AuthorizationContext,
    AuthorizationDecision,
    AuthorizationPolicyService,
)
from ...domain.authorization.permissions import Permission
from ...domain.authorization.policies import default_policy
from ...domain.identity.principal import Principal


class PolicyAuthorizer:
    """Authorization port implementation backed by a policy."""

    def __init__(self, service: AuthorizationPolicyService | None = None) -> None:
        self._service = service or AuthorizationPolicyService(default_policy())

    def authorize(
        self,
        principal: Principal,
        permission: Permission,
        resource: object | None = None,
        context: AuthorizationContext | None = None,
    ) -> AuthorizationDecision:
        return self._service.decide(principal, permission, resource, context)
