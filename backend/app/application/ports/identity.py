"""Identity and authorization ports.

These are the seams a real identity provider or policy engine plugs into.  They
speak only in domain types (``Principal``, ``Permission``, ``AuthorizationDecision``)
and the application-owned ``RequestContext`` — never in HTTP request objects.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.authorization.authorization_service import (
    AuthorizationContext,
    AuthorizationDecision,
)
from ...domain.authorization.permissions import Permission
from ...domain.identity.identity import RequestContext
from ...domain.identity.principal import Principal


@runtime_checkable
class AuthProvider(Protocol):
    """Resolves the acting principal for a request."""

    def resolve_current_principal(self, context: RequestContext) -> Principal: ...


@runtime_checkable
class AuthorizationPort(Protocol):
    """Decides whether a principal may perform an action on a resource."""

    def authorize(
        self,
        principal: Principal,
        permission: Permission,
        resource: object | None = None,
        context: AuthorizationContext | None = None,
    ) -> AuthorizationDecision: ...
