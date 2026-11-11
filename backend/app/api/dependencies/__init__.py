"""FastAPI dependencies: the single composition boundary for the request.

This is the *only* place a principal is resolved and the *only* place the wired
container is exposed to routers.  Routers receive services and the principal via
these dependencies; they never construct either themselves.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from ...application.ports.identity import AuthProvider
from ...composition import Container
from ...domain.identity.identity import RequestContext
from ...domain.identity.principal import Principal


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_request_context(request: Request) -> RequestContext:
    return RequestContext(
        headers=tuple(request.headers.items()),
        client=request.client.host if request.client else None,
        path=request.url.path,
    )


def get_current_principal(
    container: Annotated[Container, Depends(get_container)],
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> Principal:
    """Resolve the acting principal through the configured AuthProvider."""
    provider: AuthProvider = container.auth_provider  # type: ignore[assignment]
    return provider.resolve_current_principal(context)


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]
ContainerDep = Annotated[Container, Depends(get_container)]
