"""Daily briefing application service.

Generates a briefing from persisted tasks: today's responsibilities, upcoming
deadlines, overdue items, important recurring obligations within a short horizon,
and a one-sentence look-ahead.  No server-side PDF is produced; the frontend
prints the page.
"""
from __future__ import annotations

from datetime import date, timedelta

from ...domain.authorization.permissions import Permission
from ...domain.shared.clock import Clock
from ...domain.shared.errors import AuthorizationError
from ...domain.tasks.enums import TaskStatus, Urgency
from ..dto import BriefingDTO, TaskDTO
from ..ports.identity import AuthorizationPort
from ..ports.persistence import DatabaseFactoryPort, TaskQuery
from ._task_view import to_task_dto

#: How far ahead the briefing looks for upcoming and recurring obligations.
LOOK_AHEAD_DAYS = 14
_FAR_FUTURE = date(9999, 12, 31)


class BriefingService:
    def __init__(self, database: DatabaseFactoryPort, authorizer: AuthorizationPort, clock: Clock) -> None:
        self._database = database
        self._authorizer = authorizer
        self._clock = clock

    def _authorize(self, principal, permission: Permission) -> None:
        decision = self._authorizer.authorize(principal, permission)
        if not decision.allowed:
            raise AuthorizationError(decision.reason, code=decision.code)

    def build_briefing(self, principal) -> BriefingDTO:
        self._authorize(principal, Permission.BRIEFING_READ)
        with self._database.create() as uow:
            settings = uow.settings.get(principal.id)
            timezone = settings.timezone if settings else principal.timezone
            warning_window = settings.warning_window_days if settings else 3
            today = self._clock.today(timezone)
            horizon = today + timedelta(days=LOOK_AHEAD_DAYS)

            active = uow.tasks.list(TaskQuery(status=TaskStatus.OPEN), principal.id)
            dtos = [
                to_task_dto(uow, t, owner_id=principal.id, today=today, warning_window=warning_window)
                for t in active
            ]

            today_items = [d for d in dtos if d.urgency in (Urgency.OVERDUE, Urgency.DUE)]
            overdue = [d for d in dtos if d.urgency is Urgency.OVERDUE]
            upcoming = [
                d
                for d in dtos
                if d.due_date is not None and today < d.due_date <= horizon and d.urgency is not Urgency.OVERDUE
            ]
            recurring = [
                d for d in dtos if d.recurrence is not None and d.due_date is not None and d.due_date <= horizon
            ]

            return BriefingDTO(
                date=today,
                timezone=timezone,
                today=self._sort(today_items),
                upcoming=self._sort(upcoming),
                overdue=self._sort(overdue),
                recurring_obligations=self._sort(recurring),
                look_ahead=self._look_ahead(today_items, overdue, upcoming, recurring),
            )

    @staticmethod
    def _sort(dtos: list[TaskDTO]) -> list[TaskDTO]:
        return sorted(dtos, key=lambda d: (d.due_date is None, d.due_date or _FAR_FUTURE))

    @staticmethod
    def _look_ahead(today_items, overdue, upcoming, recurring) -> str:  # noqa: ANN001
        if not today_items and not upcoming and not recurring:
            return "Clear picture: no responsibilities due in the next two weeks."
        parts: list[str] = []
        if overdue:
            parts.append(f"{len(overdue)} item(s) already overdue")
        due_today = [d for d in today_items if d.urgency is Urgency.DUE]
        if due_today:
            parts.append(f"{len(due_today)} due today")
        if upcoming:
            next_item = upcoming[0]
            parts.append(
                f"{len(upcoming)} coming up in the next {LOOK_AHEAD_DAYS} days, "
                f"starting with {next_item.title!r} on {next_item.due_date:%d %b}"
            )
        if recurring:
            parts.append(f"{len(recurring)} recurring obligation(s) in the same window")
        return "; ".join(parts).capitalize() + "."
