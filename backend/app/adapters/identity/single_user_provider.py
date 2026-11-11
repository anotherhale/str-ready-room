"""Demo single-user authentication adapter.

Returns one configured operator identity.  It performs **no** credential
challenge and creates no login/session/token flow.  It is a development/demo
identity adapter and is replaceable by a session/OIDC adapter without touching
application services (see DECISIONS D-007).
"""
from __future__ import annotations

from ...domain.identity.identity import RequestContext
from ...domain.identity.principal import Principal
from ...domain.settings.entities import DEFAULT_TIMEZONE


class SingleUserAuthProvider:
    """Always resolves the one configured operator principal."""

    scheme = "single-user-demo"

    def __init__(
        self,
        *,
        user_id: str,
        display_name: str,
        timezone: str = DEFAULT_TIMEZONE,
        roles: frozenset[str] | None = None,
    ) -> None:
        self._principal = Principal(
            id=user_id,
            display_name=display_name,
            timezone=timezone,
            roles=roles if roles is not None else frozenset({"operator"}),
        )

    def resolve_current_principal(self, context: RequestContext) -> Principal:
        # No credentials are inspected; the demo identity is fixed by config.
        return self._principal
