"""Settings, category, recurrence, and demo-reset endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Response, status

from ...application.commands import (
    CreateCategoryCommand,
    RecurrenceInput,
    UpdateCategoryCommand,
    UpdateSettingsCommand,
)
from ...schemas.requests import (
    CategoryCreateRequest,
    CategoryUpdateRequest,
    RecurrencePreviewRequest,
    SettingsUpdateRequest,
)
from ...schemas.responses import (
    CategoryResponse,
    RecurrenceOverviewItem,
    RecurrenceOverviewResponse,
    RecurrencePreviewResponse,
    ResetResponse,
    SettingsResponse,
    UpcomingOccurrenceResponse,
)
from ..dependencies import ContainerDep, CurrentPrincipal

router = APIRouter(tags=["settings"])


# -- settings -------------------------------------------------------------
@router.get("/settings", response_model=SettingsResponse)
def get_settings(container: ContainerDep, principal: CurrentPrincipal) -> SettingsResponse:
    return SettingsResponse.model_validate(container.settings_service.get_settings(principal))


@router.patch("/settings", response_model=SettingsResponse)
def update_settings(
    payload: SettingsUpdateRequest, container: ContainerDep, principal: CurrentPrincipal
) -> SettingsResponse:
    command = UpdateSettingsCommand(
        warning_window_days=payload.warning_window_days, timezone=payload.timezone
    )
    return SettingsResponse.model_validate(container.settings_service.update_settings(principal, command))


# -- categories -----------------------------------------------------------
@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(container: ContainerDep, principal: CurrentPrincipal) -> list[CategoryResponse]:
    items = container.categories.list_categories(principal, include_inactive=True)
    return [CategoryResponse.model_validate(c) for c in items]


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreateRequest, container: ContainerDep, principal: CurrentPrincipal
) -> CategoryResponse:
    dto = container.categories.create_category(principal, CreateCategoryCommand(name=payload.name))
    return CategoryResponse.model_validate(dto)


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: str, payload: CategoryUpdateRequest, container: ContainerDep, principal: CurrentPrincipal
) -> CategoryResponse:
    command = UpdateCategoryCommand(name=payload.name, active=payload.active)
    dto = container.categories.update_category(principal, category_id, command)
    return CategoryResponse.model_validate(dto)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: str, container: ContainerDep, principal: CurrentPrincipal) -> Response:
    container.categories.delete_category(principal, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -- recurrence -----------------------------------------------------------
@router.get("/recurrence", response_model=RecurrenceOverviewResponse)
def recurrence_overview(container: ContainerDep, principal: CurrentPrincipal) -> RecurrenceOverviewResponse:
    dto = container.recurrence.overview(principal)
    return RecurrenceOverviewResponse(
        rules=[RecurrenceOverviewItem.model_validate(r) for r in dto.rules],
        upcoming=[UpcomingOccurrenceResponse(name=name, date=when) for name, when in dto.upcoming],
    )


@router.post("/recurrence/preview", response_model=RecurrencePreviewResponse)
def recurrence_preview(
    payload: RecurrencePreviewRequest, container: ContainerDep, principal: CurrentPrincipal
) -> RecurrencePreviewResponse:
    recurrence = RecurrenceInput(
        name=payload.name,
        frequency=payload.frequency,
        interval=payload.interval,
        day_of_week=payload.day_of_week,
        anchor_date=payload.anchor_date,
        end_type=payload.end_type,
        end_count=payload.end_count,
        end_date=payload.end_date,
        active=payload.active,
    )
    dates = container.recurrence.preview(principal, recurrence, count=payload.count)
    return RecurrencePreviewResponse(dates=dates)


# -- demo -----------------------------------------------------------------
@router.post("/demo/reset", response_model=ResetResponse)
def demo_reset(container: ContainerDep, principal: CurrentPrincipal) -> ResetResponse:
    result = container.demo.reset(principal)
    return ResetResponse.model_validate(result)
