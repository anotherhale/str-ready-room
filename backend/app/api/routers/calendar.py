"""Calendar endpoints: agenda, status, sync, create/delete, capture.

Thin inbound adapters: they validate shape with Pydantic, resolve the principal
through the shared dependency, call the application service, and serialize the
result.  No business rules live here.
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Response, status

from ...application.commands import CalendarEventCreateCommand, CaptureCalendarEventCommand
from ...schemas.requests import CalendarCaptureRequest, CalendarEventCreateRequest
from ...schemas.responses import (
    CalendarAgendaResponse,
    CalendarEventResponse,
    CalendarStatusResponse,
    CalendarSyncResponse,
    TaskResponse,
)
from ..dependencies import ContainerDep, CurrentPrincipal

router = APIRouter(tags=["calendar"])


@router.get("/calendar/agenda", response_model=CalendarAgendaResponse)
def calendar_agenda(
    container: ContainerDep,
    principal: CurrentPrincipal,
    days: int = Query(default=7, ge=1, le=90),
) -> CalendarAgendaResponse:
    """Cached events from today through ``days`` ahead, newest-not-first by time."""
    dto = container.calendar.agenda(principal, days=days)
    return CalendarAgendaResponse(
        date=dto.date,
        timezone=dto.timezone,
        window_days=dto.window_days,
        available=dto.available,
        events=[CalendarEventResponse.model_validate(e) for e in dto.events],
        detail=dto.detail,
    )


@router.get("/calendar/status", response_model=CalendarStatusResponse)
def calendar_status(container: ContainerDep, principal: CurrentPrincipal) -> CalendarStatusResponse:
    dto = container.calendar.status(principal)
    return CalendarStatusResponse.model_validate(dto, from_attributes=True)


@router.post("/calendar/sync", response_model=CalendarSyncResponse)
def calendar_sync(container: ContainerDep, principal: CurrentPrincipal) -> CalendarSyncResponse:
    """Refresh the cache from the provider (best-effort; 502 when unavailable)."""
    dto = container.calendar.sync(principal)
    return CalendarSyncResponse.model_validate(dto, from_attributes=True)


@router.post("/calendar/events", response_model=CalendarEventResponse, status_code=status.HTTP_201_CREATED)
def create_calendar_event(
    payload: CalendarEventCreateRequest, container: ContainerDep, principal: CurrentPrincipal
) -> CalendarEventResponse:
    command = CalendarEventCreateCommand(
        summary=payload.summary,
        start=payload.start,
        end=payload.end,
        all_day=payload.all_day,
        location=payload.location,
        description=payload.description,
        calendar_id=payload.calendar_id,
    )
    dto = container.calendar.create_event(principal, command)
    return CalendarEventResponse.model_validate(dto, from_attributes=True)


@router.delete("/calendar/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_calendar_event(
    event_id: str, container: ContainerDep, principal: CurrentPrincipal
) -> Response:
    container.calendar.delete_event(principal, event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/calendar/events/{event_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def capture_calendar_event(
    event_id: str,
    payload: CalendarCaptureRequest,
    container: ContainerDep,
    principal: CurrentPrincipal,
) -> TaskResponse:
    """Capture an event into a responsibility (idempotent for a linked event)."""
    command = CaptureCalendarEventCommand(
        event_id=event_id,
        category=payload.category,
        priority=payload.priority,
        due_date=payload.due_date,
        title=payload.title,
        description=payload.description,
    )
    dto = container.calendar.capture_event(principal, command)
    return TaskResponse.model_validate(dto)
