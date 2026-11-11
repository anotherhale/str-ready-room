"""Health and identity endpoints (no authorization required)."""
from __future__ import annotations

from fastapi import APIRouter

from ...schemas.responses import HealthResponse, PrincipalResponse
from ..dependencies import ContainerDep, CurrentPrincipal

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(container: ContainerDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=container.settings.environment,
        database_adapter=container.settings.db_adapter,
        auth_provider=container.settings.auth_provider,
    )


@router.get("/me", response_model=PrincipalResponse)
def whoami(principal: CurrentPrincipal) -> PrincipalResponse:
    return PrincipalResponse(
        id=principal.id,
        display_name=principal.display_name,
        timezone=principal.timezone,
        roles=sorted(principal.roles),
    )
