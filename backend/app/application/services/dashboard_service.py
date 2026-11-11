"""Dashboard application service.

Builds the operational scan: Today, Watch (within the configured warning
window), and On the Horizon, plus compact counts and a readiness summary.  Every
value is derived from persisted tasks for the current operator.
"""
from __future__ import annotations

from datetime import date, timedelta

from ...domain.authorization.permissions import Permission
from ...domain.shared.clock import Clock
from ...domain.shared.errors import AuthorizationError
from ...domain.tasks.enums import TaskStatus, Urgency
from ..dto import CountsDTO, DashboardDTO, TaskDTO
from ..ports.identity import AuthorizationPort
from ..ports.persistence import DatabaseFactoryPort, TaskQuery
from ._task_view import to_task_dto

_FAR_FUTURE = date(9999, 12, 31)


class DashboardService:
    def __init__(self, database: DatabaseFactoryPort, authorizer: AuthorizationPort, clock: Clock) -> None:
        self._database = database
        self._authorizer = authorizer
        self._clock = clock

    def _authorize(self, principal, permission: Permission) -> None:
        decision = self._authorizer.authorize(principal, permission)
        if not decision.allowed:
            raise AuthorizationError(decision.reason, code=decision.code)

    def build_dashboard(self, principal) -> DashboardDTO:
        self._authorize(principal, Permission.DASHBOARD_READ)
        with self._database.create() as uow:
            settings = uow.settings.get(principal.id)
            timezone = settings.timezone if settings else principal.timezone
            warning_window = settings.warning_window_days if settings else 3
            today = self._clock.today(timezone)

            active = uow.tasks.list(TaskQuery(status=TaskStatus.OPEN), principal.id)
            completed = uow.tasks.list(TaskQuery(status=TaskStatus.COMPLETED), principal.id)

            today_tasks: list[TaskDTO] = []
            watch_tasks: list[TaskDTO] = []
            horizon_tasks: list[TaskDTO] = []

            for task in active:
                dto = to_task_dto(
                    uow, task, owner_id=principal.id, today=today, warning_window=warning_window
                )
                if dto.urgency in (Urgency.OVERDUE, Urgency.DUE):
                    today_tasks.append(dto)
                elif dto.urgency is Urgency.WATCH:
                    watch_tasks.append(dto)
                elif dto.urgency is Urgency.UP_NEXT:
                    horizon_tasks.append(dto)
                # Urgency.NORMAL (no due date) is intentionally omitted from the
                # scan; it stays available in the inventory.

            completed_this_week = self._completed_this_week(completed, today)

            counts = CountsDTO(
                overdue=sum(1 for d in today_tasks if d.urgency is Urgency.OVERDUE),
                due=sum(1 for d in today_tasks if d.urgency is Urgency.DUE),
                watch=len(watch_tasks),
                horizon=len(horizon_tasks),
                completed_this_week=completed_this_week,
            )

            return DashboardDTO(
                today=today,
                timezone=timezone,
                greeting_name=principal.first_name,
                warning_window_days=warning_window,
                watch_label=f"{warning_window}-Day Watch",
                readiness_summary=self._readiness_summary(counts),
                counts=counts,
                today_tasks=self._sort(today_tasks),
                watch_tasks=self._sort(watch_tasks),
                horizon_tasks=self._sort(horizon_tasks),
            )

    @staticmethod
    def _completed_this_week(completed, today):  # noqa: ANN001
        start = today - timedelta(days=today.weekday())
        count = 0
        for task in completed:
            if task.completed_at is None:
                continue
            if task.completed_at.date() >= start:
                count += 1
        return count

    @staticmethod
    def _sort(dtos: list[TaskDTO]) -> list[TaskDTO]:
        return sorted(dtos, key=lambda d: (d.due_date is None, d.due_date or _FAR_FUTURE))

    @staticmethod
    def _readiness_summary(counts: CountsDTO) -> str:
        parts: list[str] = []
        if counts.overdue:
            parts.append(f"{counts.overdue} overdue")
        if counts.due:
            parts.append(f"{counts.due} due today")
        if counts.watch:
            parts.append(f"{counts.watch} on watch")
        if counts.horizon:
            parts.append(f"{counts.horizon} on the horizon")
        if not parts:
            return "All clear — nothing requires your attention right now."
        return "Operational picture: " + ", ".join(parts) + "."
