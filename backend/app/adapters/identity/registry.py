"""Identity adapter registry.

Selects the concrete ``AuthProvider`` from configuration.  This is the only
place that knows which authentication adapter is in use.
"""
from __future__ import annotations

from collections.abc import Callable

from ...application.ports.identity import AuthProvider
from ...domain.identity.identity import RequestContext
from ...domain.identity.principal import Principal
from .single_user_provider import SingleUserAuthProvider

AuthProviderFactory = Callable[[], object]


def build_auth_provider(settings) -> AuthProvider:  # noqa: ANN001 - config object
    """Return the configured authentication provider."""
    provider = settings.auth_provider
    if provider == "single_user":
        return SingleUserAuthProvider(
            user_id=settings.operator_id,
            display_name=settings.operator_display_name,
            timezone=settings.default_timezone,
        )
    raise ValueError(f"Unknown auth provider: {provider!r}")


__all__ = ["AuthProviderFactory", "SingleUserAuthProvider", "build_auth_provider", "Principal", "RequestContext"]
