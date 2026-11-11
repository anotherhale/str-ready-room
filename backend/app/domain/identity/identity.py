"""Identity value objects: roles and the request context passed to providers."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .principal import Principal


class Role(str, Enum):
    """Coarse-grained role used by authorization policies."""

    OPERATOR = "operator"
    VIEWER = "viewer"


@dataclass(frozen=True)
class RequestContext:
    """Application-owned context for resolving a principal.

    This intentionally carries only primitives so that an authentication
    adapter never has to leak an HTTP request object into the application
    layer.
    """

    headers: tuple[tuple[str, str], ...] = ()
    client: str | None = None
    path: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()

    def header(self, name: str) -> str | None:
        lowered = name.lower()
        for key, value in self.headers:
            if key.lower() == lowered:
                return value
        return None


@dataclass(frozen=True)
class AuthenticationResult:
    """Outcome of an authentication attempt."""

    principal: Principal | None = None
    authenticated: bool = False
    scheme: str = "none"
    detail: str | None = None

    @classmethod
    def anonymous(cls, detail: str | None = None) -> AuthenticationResult:
        return cls(principal=None, authenticated=False, scheme="none", detail=detail)
