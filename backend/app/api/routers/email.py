"""Mailbox endpoints: list, read, status, capture.

Thin inbound adapters.  The mailbox is read-only: there is deliberately no
send/move/delete endpoint (see DECISIONS D-026).
"""
from __future__ import annotations

from fastapi import APIRouter, Query, status

from ...application.commands import CaptureEmailCommand
from ...schemas.requests import EmailCaptureRequest
from ...schemas.responses import (
    EmailMessageResponse,
    EmailSummaryResponse,
    MailboxStatusResponse,
    TaskResponse,
)
from ..dependencies import ContainerDep, CurrentPrincipal

router = APIRouter(tags=["email"])


@router.get("/mail/messages", response_model=list[EmailSummaryResponse])
def list_messages(
    container: ContainerDep,
    principal: CurrentPrincipal,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[EmailSummaryResponse]:
    """Recent messages, newest first, each annotated with capture provenance."""
    dtos = container.email.list_messages(principal, limit=limit)
    return [EmailSummaryResponse.model_validate(dto, from_attributes=True) for dto in dtos]


@router.get("/mail/status", response_model=MailboxStatusResponse)
def mailbox_status(container: ContainerDep, principal: CurrentPrincipal) -> MailboxStatusResponse:
    dto = container.email.status(principal)
    return MailboxStatusResponse.model_validate(dto, from_attributes=True)


@router.get("/mail/messages/{message_id}", response_model=EmailMessageResponse)
def read_message(
    message_id: str, container: ContainerDep, principal: CurrentPrincipal
) -> EmailMessageResponse:
    dto = container.email.get_message(principal, message_id)
    return EmailMessageResponse.model_validate(dto, from_attributes=True)


@router.post(
    "/mail/messages/{message_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def capture_message(
    message_id: str,
    payload: EmailCaptureRequest,
    container: ContainerDep,
    principal: CurrentPrincipal,
) -> TaskResponse:
    """Capture a message into a responsibility (idempotent for a captured message)."""
    command = CaptureEmailCommand(
        message_id=message_id,
        category=payload.category,
        priority=payload.priority,
        due_date=payload.due_date,
        title=payload.title,
    )
    dto = container.email.capture_message(principal, command)
    return TaskResponse.model_validate(dto)
