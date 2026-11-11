"""Task endpoints: list, detail, create, update, complete, reopen, delete.

Thin inbound adapters: validate shape, invoke the application service, map the
result DTO to a response schema.  No business rules or database access here.
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Response, status

from ...application.commands import (
    CreateTaskCommand,
    ListTasksQuery,
    RecurrenceInput,
    UpdateTaskCommand,
)
from ...schemas.requests import RecurrenceRequest, TaskCreateRequest, TaskUpdateRequest
from ...schemas.responses import TaskListResponse, TaskResponse
from ..dependencies import ContainerDep, CurrentPrincipal

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _to_recurrence_input(payload: RecurrenceRequest | None) -> RecurrenceInput | None:
    if payload is None:
        return None
    return RecurrenceInput(
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


@router.get("", response_model=TaskListResponse)
def list_tasks(
    container: ContainerDep,
    principal: CurrentPrincipal,
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str = Query(default="due_date"),
) -> TaskListResponse:
    query = ListTasksQuery(status=status_filter, category=category, search=search, sort=sort)
    items = container.tasks.list_tasks(principal, query)
    return TaskListResponse(items=[TaskResponse.model_validate(i) for i in items], total=len(items))


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreateRequest, container: ContainerDep, principal: CurrentPrincipal
) -> TaskResponse:
    command = CreateTaskCommand(
        title=payload.title,
        category=payload.category,
        priority=payload.priority,
        description=payload.description,
        due_date=payload.due_date,
        recurrence=_to_recurrence_input(payload.recurrence),
    )
    dto = container.tasks.create_task(principal, command)
    return TaskResponse.model_validate(dto)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, container: ContainerDep, principal: CurrentPrincipal) -> TaskResponse:
    return TaskResponse.model_validate(container.tasks.get_task(principal, task_id))


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str, payload: TaskUpdateRequest, container: ContainerDep, principal: CurrentPrincipal
) -> TaskResponse:
    command = UpdateTaskCommand(
        title=payload.title,
        description=payload.description,
        description_provided=payload.description_set,
        category=payload.category,
        priority=payload.priority,
        due_date=payload.due_date,
        due_date_provided=payload.due_date_set,
        recurrence_provided=payload.recurrence_set,
        recurrence=_to_recurrence_input(payload.recurrence),
    )
    dto = container.tasks.update_task(principal, task_id, command)
    return TaskResponse.model_validate(dto)


@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task(task_id: str, container: ContainerDep, principal: CurrentPrincipal) -> TaskResponse:
    return TaskResponse.model_validate(container.tasks.complete_task(principal, task_id))


@router.post("/{task_id}/reopen", response_model=TaskResponse)
def reopen_task(task_id: str, container: ContainerDep, principal: CurrentPrincipal) -> TaskResponse:
    return TaskResponse.model_validate(container.tasks.reopen_task(principal, task_id))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, container: ContainerDep, principal: CurrentPrincipal) -> Response:
    container.tasks.delete_task(principal, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
