"""Mailbox application service: list, read, and capture messages into tasks.

The service depends on the ``MailboxProvider`` port (not ``imaplib``) and on
persistence ports.  It never imports a concrete adapter, an ORM model, or
FastAPI.

Scope (see DECISIONS D-026): the mailbox is **read-only**.  There is no send,
move, or delete path.  Capture is operator-initiated and writes one provenance
row (``EmailSource``) so a captured message is marked and cannot silently spawn
duplicates; recapturing reuses the single row.
"""
from __future__ import annotations

from ...domain.authorization.permissions import Permission
from ...domain.shared.clock import Clock
from ...domain.shared.errors import AuthorizationError, ValidationError
from ...domain.tasks.entities import Task
from ...domain.tasks.enums import Priority
from ...domain.tasks.value_objects import normalize_category
from ...mailbox.entities import EmailSource
from ...mailbox.providers.base import MailboxError, MailboxProvider
from ..commands import CaptureEmailCommand
from ..dto import EmailMessageDTO, EmailSummaryDTO, MailboxStatusDTO, TaskDTO
from ..ports.clock import IdGenerator
from ..ports.identity import AuthorizationPort
from ..ports.persistence import DatabaseFactoryPort
from ._task_view import to_task_dto

#: Keep only this much of a captured body on the task description.
_MAX_CAPTURED_BODY = 2000


class EmailService:
    def __init__(
        self,
        database: DatabaseFactoryPort,
        authorizer: AuthorizationPort,
        clock: Clock,
        ids: IdGenerator,
        provider: MailboxProvider | None = None,
        mailbox_name: str = "INBOX",
    ) -> None:
        self._database = database
        self._authorizer = authorizer
        self._clock = clock
        self._ids = ids
        self._provider = provider
        self._mailbox_name = mailbox_name

    # -- authorization -------------------------------------------------
    def _authorize(self, principal, permission: Permission) -> None:  # noqa: ANN001
        decision = self._authorizer.authorize(principal, permission)
        if not decision.allowed:
            raise AuthorizationError(decision.reason, code=decision.code)

    @property
    def available(self) -> bool:
        return self._provider is not None

    # -- read ----------------------------------------------------------
    def list_messages(self, principal, *, limit: int = 20) -> list[EmailSummaryDTO]:  # noqa: ANN001
        """List recent messages, annotated with capture provenance."""
        self._authorize(principal, Permission.EMAIL_READ)
        if self._provider is None:
            raise MailboxError("Mailbox integration is not configured.", status=502, code="unavailable")

        summaries = self._provider.list_messages(limit=max(1, min(limit, 100)))
        with self._database.create() as uow:
            captured = {s.message_id: s.task_id for s in uow.email_sources.list(principal.id)}

        return [
            EmailSummaryDTO(
                message_id=summary.message_id,
                sender=summary.sender,
                subject=summary.subject,
                received_at=summary.received_at,
                snippet=summary.snippet,
                captured=summary.message_id in captured,
                task_id=captured.get(summary.message_id),
            )
            for summary in summaries
        ]

    def get_message(self, principal, message_id: str) -> EmailMessageDTO:  # noqa: ANN001
        self._authorize(principal, Permission.EMAIL_READ)
        if self._provider is None:
            raise MailboxError("Mailbox integration is not configured.", status=502, code="unavailable")

        message = self._provider.get_message(message_id)
        with self._database.create() as uow:
            source = uow.email_sources.get_by_message_id(message.message_id, principal.id)
            captured = source is not None
            task_id = source.task_id if source is not None else None
        return EmailMessageDTO(
            message_id=message.message_id,
            sender=message.sender,
            subject=message.subject,
            received_at=message.received_at,
            body=message.body,
            captured=captured,
            task_id=task_id,
        )

    def status(self, principal) -> MailboxStatusDTO:  # noqa: ANN001
        self._authorize(principal, Permission.EMAIL_READ)
        with self._database.create() as uow:
            captured_count = uow.email_sources.count(principal.id)

        provider = self._provider
        available = provider is not None
        message_count = 0
        detail = None
        if provider is not None:
            try:
                message_count = len(provider.list_messages(limit=100))
            except MailboxError as exc:
                available = False
                detail = exc.message
        else:
            detail = "Mailbox integration is not configured."

        return MailboxStatusDTO(
            available=available,
            provider=provider.name if provider is not None else None,
            mailbox=self._mailbox_name if provider is not None else None,
            message_count=message_count,
            captured_count=captured_count,
            detail=detail,
        )

    # -- capture (message -> responsibility) ---------------------------
    def capture_message(self, principal, command: CaptureEmailCommand) -> TaskDTO:  # noqa: ANN001
        """Create a task from a message, or reuse the one already linked to it."""
        self._authorize(principal, Permission.EMAIL_CAPTURE)
        if self._provider is None:
            raise MailboxError("Mailbox integration is not configured.", status=502, code="unavailable")

        message = self._provider.get_message(command.message_id)
        now = self._clock.now_utc()

        with self._database.create() as uow:
            settings = uow.settings.get(principal.id)
            timezone = settings.timezone if settings is not None else principal.timezone
            warning_window = settings.warning_window_days if settings is not None else 3
            today = self._clock.today(timezone)

            existing_source = uow.email_sources.get_by_message_id(message.message_id, principal.id)
            if existing_source is not None and existing_source.task_id is not None:
                existing_task = uow.tasks.get_by_id(existing_source.task_id, principal.id)
                if existing_task is not None:
                    # Idempotent: a captured message keeps its single live task.
                    return to_task_dto(
                        uow, existing_task, owner_id=principal.id, today=today,
                        warning_window=warning_window,
                    )

            title = (command.title or message.subject or "Email").strip() or "Email"
            description = self._describe(message)
            task = Task.create(
                id=self._ids.new_id(),
                owner_id=principal.id,
                title=title,
                category=normalize_category(command.category or self._default_category(uow, principal)),
                now=now,
                priority=command.priority or Priority.NORMAL,
                description=description,
                due_date=command.due_date,
            )
            uow.tasks.save(task)

            # Reuse the single source row on recapture (DECISIONS D-026).
            source = existing_source or EmailSource(
                id=self._ids.new_id(),
                owner_id=principal.id,
                message_id=message.message_id,
            )
            source.task_id = task.id
            source.sender = message.sender
            source.subject = message.subject
            source.received_at = message.received_at
            source.captured_at = now
            uow.email_sources.save(source)
            uow.commit()

            return to_task_dto(
                uow, task, owner_id=principal.id, today=today, warning_window=warning_window
            )

    # -- helpers -------------------------------------------------------
    def _default_category(self, uow, principal) -> str:  # noqa: ANN001
        categories = uow.categories.list(principal.id)
        return categories[0].name if categories else "General"

    def _describe(self, message) -> str:  # noqa: ANN001
        header = f"Captured from email\nFrom: {message.sender}\nSubject: {message.subject}"
        body = (message.body or "").strip()[:_MAX_CAPTURED_BODY]
        if not body:
            raise ValidationError("Message has no readable body to capture")
        return f"{header}\n\n{body}"
