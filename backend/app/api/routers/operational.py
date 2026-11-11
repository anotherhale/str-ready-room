"""Dashboard and briefing endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ...schemas.responses import BriefingResponse, CountsResponse, DashboardResponse, TaskResponse
from ..dependencies import ContainerDep, CurrentPrincipal

router = APIRouter(tags=["operational"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(container: ContainerDep, principal: CurrentPrincipal) -> DashboardResponse:
    dto = container.dashboard.build_dashboard(principal)
    return DashboardResponse(
        today=dto.today,
        timezone=dto.timezone,
        greeting_name=dto.greeting_name,
        warning_window_days=dto.warning_window_days,
        watch_label=dto.watch_label,
        readiness_summary=dto.readiness_summary,
        counts=CountsResponse.model_validate(dto.counts),
        today_tasks=[TaskResponse.model_validate(t) for t in dto.today_tasks],
        watch_tasks=[TaskResponse.model_validate(t) for t in dto.watch_tasks],
        horizon_tasks=[TaskResponse.model_validate(t) for t in dto.horizon_tasks],
    )


@router.get("/briefing", response_model=BriefingResponse)
def get_briefing(container: ContainerDep, principal: CurrentPrincipal) -> BriefingResponse:
    dto = container.briefing.build_briefing(principal)
    return BriefingResponse(
        date=dto.date,
        timezone=dto.timezone,
        today=[TaskResponse.model_validate(t) for t in dto.today],
        upcoming=[TaskResponse.model_validate(t) for t in dto.upcoming],
        overdue=[TaskResponse.model_validate(t) for t in dto.overdue],
        recurring_obligations=[TaskResponse.model_validate(t) for t in dto.recurring_obligations],
        look_ahead=dto.look_ahead,
    )
