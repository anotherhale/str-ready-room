"""Calendar application service: sync, agenda, status, create/delete, capture.

The service depends on the ``CalendarProvider`` port and on persistence ports;
it never imports a concrete adapter, an ORM model, or FastAPI.  Every operation
enforces authorization before doing protected work.

Design notes (see DECISIONS D-025, D-030, D-032):

* the backend keeps its **own cache** of events; the UI reads only the cache;
* sync is the only thing that talks to the provider for reads, and it is
  best-effort — an unreachable provider surfaces as an "unavailable" state
  rather than failing the rest of the app;
* a locally created event is cached under the provider's **canonical** calendar
  id (resolved through the port) so a later sync updates the same row instead of
  deleting and re-inserting it — which would silently drop the capture link;
* capture is idempotent: an already-linked event returns its existing task.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from ...calendar.domain import CalendarEvent
from ...calendar.entities import CalendarEventRecord
from ...calendar.providers.base import CalendarError, CalendarProvider
from ...domain.authorization.permissions import Permission
from ...domain.shared.clock import Clock
from ...domain.shared.errors import AuthorizationError, NotFoundError, ValidationError
from ...domain.tasks.entities import Task
from ...domain.tasks.enums import Priority
from ...domain.tasks.value_objects import normalize_category
from ..commands import CalendarEventCreateCommand, CaptureCalendarEventCommand
from ..dto import (
    CalendarAgendaDTO,
    CalendarEventDTO,
    CalendarStatusDTO,
    CalendarSyncResultDTO,
    TaskDTO,
)
from ..ports.clock import IdGenerator
from ..ports.identity import AuthorizationPort
from ..ports.persistence import DatabaseFactoryPort
from ._task_view import to_task_dto

#: How many days of agenda to return by default.
DEFAULT_WINDOW_DAYS = 7
#: Cap the description copied from an event so a long agenda note cannot bloat a task.
_MAX_DESCRIPTION = 2000


class CalendarService:
    def __init__(
        self,
        database: DatabaseFactoryPort,
        authorizer: AuthorizationPort,
        clock: Clock,
        ids: IdGenerator,
        provider: CalendarProvider | None = None,
        default_calendar: str = "detachment",
    ) -> None:
        self._database = database
        self._authorizer = authorizer
        self._clock = clock
        self._ids = ids
        self._provider = provider
        self._default_calendar = default_calendar

    # -- authorization -------------------------------------------------
    def _authorize(self, principal, permission: Permission) -> None:  # noqa: ANN001
        decision = self._authorizer.authorize(principal, permission)
        if not decision.allowed:
            raise AuthorizationError(decision.reason, code=decision.code)

    @property
    def available(self) -> bool:
        return self._provider is not None

    # -- settings helpers ---------------------------------------------
    def _settings(self, uow, principal):  # noqa: ANN001
        from ...domain.settings.entities import OperatorSettings

        return uow.settings.get(principal.id) or OperatorSettings(
            owner_id=principal.id, timezone=principal.timezone
        )

    # -- read ----------------------------------------------------------
    def agenda(self, principal, *, days: int = DEFAULT_WINDOW_DAYS) -> CalendarAgendaDTO:  # noqa: ANN001
        """Return cached events from today through ``days`` ahead (inclusive).

        The persisted ``start`` is naive UTC, but the operator's "today" is a
        *local* date, so the repository query uses a deliberately generous UTC
        bound (±1 day) and the exact local-date filter happens here.  Doing the
        precise filter in Python keeps it portable across dialects (no
        dialect-specific date conversion in SQL) and correct across UTC rollover.
        """
        self._authorize(principal, Permission.CALENDAR_READ)
        with self._database.create() as uow:
            settings = self._settings(uow, principal)
            today = self._clock.today(settings.timezone)
            window = max(1, min(days, 90))
            end = today + timedelta(days=window - 1)
            records = uow.calendar_events.list(
                principal.id, start=today - timedelta(days=1), end=end + timedelta(days=1)
            )
            events = [
                self._to_dto(record)
                for record in records
                if today <= record.local_date <= end
            ]
            available = self._provider is not None
            detail = None if available else "Calendar integration is not configured."
            return CalendarAgendaDTO(
                date=today,
                timezone=settings.timezone,
                window_days=window,
                available=available,
                events=events,
                detail=detail,
            )

    def status(self, principal) -> CalendarStatusDTO:  # noqa: ANN001
        self._authorize(principal, Permission.CALENDAR_READ)
        with self._database.create() as uow:
            records = uow.calendar_events.list(principal.id)
            last_synced = max((r.synced_at for r in records if r.synced_at), default=None)
            provider_name = self._provider.name if self._provider is not None else None
            detail = None if self._provider is not None else "Calendar integration is not configured."
            return CalendarStatusDTO(
                available=self._provider is not None,
                provider=provider_name,
                calendar_id=self._default_calendar if self._provider is not None else None,
                cached_events=len(records),
                last_synced_at=last_synced,
                detail=detail,
            )

    # -- sync ----------------------------------------------------------
    def sync(self, principal, *, calendar_id: str | None = None) -> CalendarSyncResultDTO:  # noqa: ANN001
        """Refresh the cache from the provider.  Best-effort; may raise CalendarError."""
        self._authorize(principal, Permission.CALENDAR_SYNC)
        if self._provider is None:
            raise CalendarError("Calendar integration is not configured.", status=502, code="unavailable")

        resolved = self._resolve_calendar(calendar_id)
        fetched = self._provider.list_events(resolved)
        now = self._clock.now_utc()
        created = updated = pruned = 0

        with self._database.create() as uow:
            keep: set[str] = set()
            for event in fetched:
                event.calendar_id = resolved
                keep.add(event.uid)
                existing = uow.calendar_events.get_by_uid(event.uid, resolved, principal.id)
                if existing is None:
                    record = CalendarEventRecord.from_event(
                        event, id=self._ids.new_id(), owner_id=principal.id, synced_at=now
                    )
                    uow.calendar_events.save(record)
                    created += 1
                else:
                    # Preserve the capture link; the provider knows nothing of it.
                    record = CalendarEventRecord.from_event(
                        event, id=existing.id, owner_id=principal.id, synced_at=now
                    )
                    record.task_id = existing.task_id
                    uow.calendar_events.save(record)
                    updated += 1
            pruned = uow.calendar_events.delete_missing(resolved, keep, principal.id)
            uow.commit()

        return CalendarSyncResultDTO(
            fetched=len(fetched), created=created, updated=updated, pruned=pruned, synced_at=now
        )

    def sync_quietly(self, principal) -> bool:  # noqa: ANN001
        """Sync for the startup path: never raises, returns whether it ran."""
        if self._provider is None:
            return False
        try:
            self.sync(principal)
            return True
        except Exception:  # noqa: BLE001 - startup must not fail on an optional service
            return False

    # -- write ---------------------------------------------------------
    def create_event(self, principal, command: CalendarEventCreateCommand) -> CalendarEventDTO:  # noqa: ANN001
        self._authorize(principal, Permission.CALENDAR_WRITE)
        if self._provider is None:
            raise CalendarError("Calendar integration is not configured.", status=502, code="unavailable")
        if not command.summary.strip():
            raise ValidationError("Event summary is required")

        now = self._clock.now_utc()
        calendar_ref = command.calendar_id or self._default_calendar
        # Resolve to the provider's canonical id *before* caching so a later
        # sync finds this row instead of replacing it (DECISIONS D-032).
        resolved = self._resolve_calendar(calendar_ref)

        # A floating (naive) local time from the UI is anchored to the operator's
        # effective timezone. Left naive, the value is ambiguous: the browser
        # re-interprets it in its own zone before formatting, so the displayed
        # time drifts (see DECISIONS D-037). The read is short and keeps the
        # provider call outside the transaction, matching ``sync``.
        with self._database.create() as uow:
            settings = self._settings(uow, principal)
            timezone_name = settings.timezone

        event = CalendarEvent(
            uid=self._ids.new_id(),
            calendar_id=resolved,
            summary=command.summary.strip(),
            start=self._anchor_local(command.start, timezone_name),
            end=self._anchor_local(command.end, timezone_name) if command.end is not None else None,
            all_day=command.all_day,
            location=command.location,
            description=command.description,
            sequence=0,
            updated_at=now,
        )
        created = self._provider.create_event(event)

        with self._database.create() as uow:
            record = CalendarEventRecord.from_event(
                created, id=self._ids.new_id(), owner_id=principal.id, synced_at=now
            )
            uow.calendar_events.save(record)
            uow.commit()
            return self._to_dto(record)

    def delete_event(self, principal, event_id: str) -> None:  # noqa: ANN001
        self._authorize(principal, Permission.CALENDAR_WRITE)
        if self._provider is None:
            raise CalendarError("Calendar integration is not configured.", status=502, code="unavailable")
        with self._database.create() as uow:
            record = uow.calendar_events.get_by_id(event_id, principal.id)
            if record is None:
                raise NotFoundError(f"Calendar event {event_id} not found")
            self._provider.delete_event(record.calendar_id, record.uid, record.href)
            uow.calendar_events.delete(event_id, principal.id)
            uow.commit()

    # -- capture (event -> responsibility) -----------------------------
    def capture_event(self, principal, command: CaptureCalendarEventCommand) -> TaskDTO:  # noqa: ANN001
        """Turn a cached event into a task; idempotent for an already-linked event."""
        self._authorize(principal, Permission.TASKS_CREATE)
        now = self._clock.now_utc()

        with self._database.create() as uow:
            record = uow.calendar_events.get_by_id(command.event_id, principal.id)
            if record is None:
                raise NotFoundError(f"Calendar event {command.event_id} not found")

            settings = self._settings(uow, principal)
            today = self._clock.today(settings.timezone)

            if record.task_id is not None:
                existing = uow.tasks.get_by_id(record.task_id, principal.id)
                if existing is not None:
                    # Idempotent: return the task already linked to this event.
                    return to_task_dto(
                        uow, existing, owner_id=principal.id, today=today,
                        warning_window=settings.warning_window_days,
                    )

            title = (command.title or record.summary).strip() or "Calendar event"
            due_date = command.due_date or record.local_date
            description = command.description
            if description is None:
                description = self._event_digest(record)

            task = Task.create(
                id=self._ids.new_id(),
                owner_id=principal.id,
                title=title,
                category=normalize_category(command.category or self._default_category(uow, principal)),
                now=now,
                priority=command.priority or Priority.NORMAL,
                description=description,
                due_date=due_date,
            )
            uow.tasks.save(task)
            record.task_id = task.id
            uow.calendar_events.save(record)
            uow.commit()

            return to_task_dto(
                uow, task, owner_id=principal.id, today=today,
                warning_window=settings.warning_window_days,
            )

    # -- helpers -------------------------------------------------------
    def _default_category(self, uow, principal) -> str:  # noqa: ANN001
        categories = uow.categories.list(principal.id)
        return categories[0].name if categories else "General"

    def _event_digest(self, record: CalendarEventRecord) -> str:
        parts = [f"From calendar: {record.summary}"]
        when = record.start_local()
        if record.all_day:
            parts.append(f"When: all day on {when.date().isoformat()}")
        else:
            parts.append(f"When: {when.strftime('%Y-%m-%d %H:%M %Z').strip()}")
        if record.location:
            parts.append(f"Where: {record.location}")
        if record.description:
            parts.append(record.description[:_MAX_DESCRIPTION])
        return "\n".join(parts)

    def _resolve_calendar(self, calendar_ref: str | None) -> str:
        ref = calendar_ref or self._default_calendar
        assert self._provider is not None
        try:
            return self._provider.resolve_calendar_id(ref)
        except CalendarError:
            return ref

    @staticmethod
    def _anchor_local(value: datetime, timezone_name: str | None) -> datetime:
        """Attach the operator's zone to a floating (naive) local wall-clock time.

        An aware value is passed through unchanged. A naive value is the
        operator's *local* time (the UI's datetime-local control), so it is
        anchored to their zone rather than left ambiguous or coerced to UTC.
        """
        if value.tzinfo is not None:
            return value
        try:
            zone = ZoneInfo(timezone_name) if timezone_name else None
        except Exception:  # noqa: BLE001 - unknown zone: leave the value floating
            zone = None
        return value.replace(tzinfo=zone) if zone is not None else value

    @staticmethod
    def _to_dto(record: CalendarEventRecord) -> CalendarEventDTO:
        return CalendarEventDTO(
            id=record.id,
            uid=record.uid,
            calendar_id=record.calendar_id,
            summary=record.summary,
            start=record.start_local(),
            end=record.end_local(),
            all_day=record.all_day,
            location=record.location,
            description=record.description,
            task_id=record.task_id,
        )


def _combine(value: date, at: time) -> datetime:  # pragma: no cover - helper
    return datetime.combine(value, at)
