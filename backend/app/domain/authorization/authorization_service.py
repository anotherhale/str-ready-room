"""Authorization decision value objects and pure decision logic."""
from __future__ import annotations

from dataclasses import dataclass

from ..identity.principal import Principal
from .permissions import Permission
from .policies import Policy


@dataclass(frozen=True)
class AuthorizationContext:
    """Optional contextual information for a decision."""

    owner_id: str | None = None
    resource_type: str | None = None


@dataclass(frozen=True)
class AuthorizationDecision:
    """The result of an authorization check."""

    allowed: bool
    permission: Permission
    reason: str
    code: str = "ok"

    @classmethod
    def allow(cls, permission: Permission, reason: str = "granted") -> AuthorizationDecision:
        return cls(allowed=True, permission=permission, reason=reason, code="ok")

    @classmethod
    def deny(cls, permission: Permission, reason: str, code: str = "forbidden") -> AuthorizationDecision:
        return cls(allowed=False, permission=permission, reason=reason, code=code)


class AuthorizationPolicyService:
    """Pure authorization evaluator.

    It answers two questions independently:

    1. Does the principal hold the required permission (policy)?
    2. Does the principal own the resource (ownership)?

    Both must pass.  Ownership is *not* a substitute for a permission check.
    """

    def __init__(self, policy: Policy) -> None:
        self._policy = policy

    @property
    def policy(self) -> Policy:
        return self._policy

    def permissions_for(self, principal: Principal) -> frozenset[Permission]:
        return self._policy.permissions_for(principal)

    def decide(
        self,
        principal: Principal,
        permission: Permission,
        resource: object | None = None,
        context: AuthorizationContext | None = None,
    ) -> AuthorizationDecision:
        if permission not in self.permissions_for(principal):
            return AuthorizationDecision.deny(
                permission, f"principal {principal.id!r} lacks {permission.value}"
            )

        owner_id = self._resolve_owner_id(resource, context)
        if owner_id is not None and owner_id != principal.id:
            return AuthorizationDecision.deny(
                permission,
                f"principal {principal.id!r} does not own resource owned by {owner_id!r}",
                code="forbidden_ownership",
            )

        return AuthorizationDecision.allow(permission)

    @staticmethod
    def _resolve_owner_id(
        resource: object | None, context: AuthorizationContext | None
    ) -> str | None:
        if context is not None and context.owner_id is not None:
            return context.owner_id
        if resource is not None:
            return getattr(resource, "owner_id", None)
        return None
