"""Authorization adapter registry.

Selects the concrete authorization adapter from configuration.
"""
from __future__ import annotations

from ...application.ports.identity import AuthorizationPort
from .policy_authorizer import PolicyAuthorizer


def build_authorizer(settings) -> AuthorizationPort:  # noqa: ANN001 - config object
    """Return the configured authorization adapter."""
    engine = settings.authorization_engine
    if engine == "policy":
        return PolicyAuthorizer()
    raise ValueError(f"Unknown authorization engine: {engine!r}")


__all__ = ["PolicyAuthorizer", "build_authorizer"]
