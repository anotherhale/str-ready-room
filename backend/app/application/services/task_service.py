"""Task application service: capture, edit, complete, reopen, delete.

Responsibilities:
* enforce authorization (permission) before protected work;
* pass the principal's id to repositories so ownership is respected;
* run multi-step workflows (complete + create successor) in one transaction;
* keep recurrence configuration coherent when editing.

It depends only on ports (persistence, authorization, clock, ids) and domain
objects.  It never imports an adapter, ORM model, or FastAPI type.
"""
from __future__ import annotations

from datetime import date, datetime

from ...domain.authorization.permissions import Permission
from ...domain.shared.clock import Clock
from ...domain.shared.errors import AuthorizationError, NotFoundError, ValidationError
from ...domain.tasks.entities import RecurrenceRule, Task
from ...domain.tasks.enums import EndType, Priority, TaskStatus
from ...domain.tasks.events import SuccessorTaskCreated
from ...domain.tasks.recurrence import plan_next
from ...domain.tasks.recurrence import preview as preview_dates
from ...domain.tasks.value_objects import normalize_category
from ..commands import CreateTaskCommand, ListTasksQuery, RecurrenceInput, UpdateTaskCommand
from ..dto import TaskDTO
from ..ports.clock import IdGenerator
from ..ports.identity import AuthorizationPort
from ..ports.persistence import DatabaseFactoryPort, TaskQuery
from ._task_view import to_task_dto

_SORT_KEYS = {"due_date", "priority", "created", "title", "urgency"}
_FAR_FUTURE = date(9999, 12, 31)


class TaskService:
    def __init__(
        self,
        database: DatabaseFactoryPort,
        authorizer: AuthorizationPort,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._database = database
        self._authorizer = authorizer
        self._clock = clock
        self._ids = ids

    # -- helpers -------------------------------------------------------
    def _authorize(self, principal, permission: Permission, resource: object | None = None) -> None:
        decision = self._authorizer.authorize(principal, permission, resource)
        if not decision.allowed:
            raise AuthorizationError(decision.reason, code=decision.code)

    def _settings(self, uow, principal):  # noqa: ANN001
        """Return the operator's settings, falling back to principal defaults.

        An operator who has never opened Settings still gets a usable warning
        window and timezone rather than an error.
        """
        settings = uow.settings.get(principal.id)
        if settings is None:
            from ...domain.settings.entities import OperatorSettings

            return OperatorSettings(
                owner_id=principal.id,
                timezone=principal.timezone,
            )
        return settings

    def _to_dto(self, task: Task, uow, principal, *, today, warning_window) -> TaskDTO:  # noqa: ANN001
        return to_task_dto(
            uow, task, owner_id=principal.id, today=today, warning_window=warning_window
        )

    # -- create --------------------------------------------------------
    def create_task(self, principal, command: CreateTaskCommand) -> TaskDTO:
        self._authorize(principal, Permission.TASKS_CREATE)
        now = self._clock.now_utc()

        with self._database.create() as uow:
            settings = self._settings(uow, principal)
            task = Task.create(
                id=self._ids.new_id(),
                owner_id=principal.id,
                title=command.title,
                category=normalize_category(command.category),
                now=now,
                priority=command.priority,
                description=command.description,
                due_date=command.due_date,
            )
            if command.recurrence is not None:
                rule = self._build_rule(command.recurrence, principal, now, anchor=command.due_date)
                uow.recurrence_rules.save(rule)
                series_id = self._ids.new_id()
                task.attach_to_series(series_id, rule.id, 1)
                rule.record_generation()
                rule.next_occurrence = plan_next(rule, task.due_date or rule.anchor_date).date
                uow.recurrence_rules.save(rule)

            uow.tasks.save(task)
            uow.commit()
            dto = self._to_dto(
                task, uow, principal, today=self._clock.today(settings.timezone),
                warning_window=settings.warning_window_days,
            )
        return dto

    # -- read ----------------------------------------------------------
    def get_task(self, principal, task_id: str) -> TaskDTO:
        self._authorize(principal, Permission.TASKS_READ)
        with self._database.create() as uow:
            task = uow.tasks.get_by_id(task_id, principal.id)
            if task is None:
                raise NotFoundError(f"Task {task_id} not found")
            settings = self._settings(uow, principal)
            return self._to_dto(
                task, uow, principal, today=self._clock.today(settings.timezone),
                warning_window=settings.warning_window_days,
            )

    def list_tasks(self, principal, query: ListTasksQuery) -> list[TaskDTO]:
        self._authorize(principal, Permission.TASKS_READ)
        criteria = self._build_query(query)
        with self._database.create() as uow:
            settings = self._settings(uow, principal)
            today = self._clock.today(settings.timezone)
            tasks = uow.tasks.list(criteria, principal.id)
            dtos = [
                self._to_dto(task, uow, principal, today=today, warning_window=settings.warning_window_days)
                for task in tasks
            ]
        return self._sort(dtos, query.sort)

    @staticmethod
    def _build_query(query: ListTasksQuery) -> TaskQuery:
        include_all = query.status == "all"
        status = None
        if not include_all:
            if query.status == TaskStatus.OPEN.value:
                status = TaskStatus.OPEN
            elif query.status == TaskStatus.COMPLETED.value:
                status = TaskStatus.COMPLETED
            elif query.status in (None, ""):
                status = TaskStatus.OPEN  # default view is the active set
            else:
                raise ValidationError(f"Unknown status filter: {query.status!r}")
        return TaskQuery(
            status=status,
            include_all_statuses=include_all,
            category=query.category,
            search=query.search,
        )

    @staticmethod
    def _sort(dtos: list[TaskDTO], sort: str) -> list[TaskDTO]:
        if sort not in _SORT_KEYS:
            raise ValidationError(f"Unknown sort key: {sort!r}")
        priority_rank = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.NORMAL: 2, Priority.LOW: 3}
        if sort == "priority":
            return sorted(dtos, key=lambda d: (priority_rank.get(d.priority, 9), d.due_date or _FAR_FUTURE))
        if sort == "created":
            return sorted(dtos, key=lambda d: d.created_at, reverse=True)
        if sort == "title":
            return sorted(dtos, key=lambda d: d.title.casefold())
        if sort == "urgency":
            order = {"overdue": 0, "due": 1, "watch": 2, "up_next": 3, "normal": 4, "completed": 5}
            return sorted(dtos, key=lambda d: (order.get(d.urgency.value, 9), d.due_date or _FAR_FUTURE))
        # due_date
        return sorted(dtos, key=lambda d: (d.due_date is None, d.due_date or _FAR_FUTURE))

    # -- update --------------------------------------------------------
    def update_task(self, principal, task_id: str, command: UpdateTaskCommand) -> TaskDTO:
        self._authorize(principal, Permission.TASKS_UPDATE)
        now = self._clock.now_utc()
        with self._database.create() as uow:
            settings = self._settings(uow, principal)
            task = uow.tasks.get_by_id(task_id, principal.id)
            if task is None:
                raise NotFoundError(f"Task {task_id} not found")

            task.update(
                now,
                title=command.title,
                description=command.description,
                description_provided=command.description_provided,
                category=normalize_category(command.category) if command.category else None,
                priority=command.priority,
                due_date=command.due_date,
                due_date_provided=command.due_date_provided,
            )

            if command.recurrence_provided:
                self._apply_recurrence_edit(uow, principal, task, command.recurrence, now)

            uow.tasks.save(task)
            uow.commit()
            return self._to_dto(
                task, uow, principal, today=self._clock.today(settings.timezone),
                warning_window=settings.warning_window_days,
            )

    def _apply_recurrence_edit(self, uow, principal, task: Task, recurrence, now: datetime) -> None:  # noqa: ANN001
        """Set, update, or detach recurrence while preserving series identity."""
        self._authorize(principal, Permission.RECURRENCE_WRITE)

        if recurrence is None:
            # Detach: deactivate the rule only if no other task references it.
            if task.recurrence_rule_id is not None:
                rule = uow.recurrence_rules.get_by_id(task.recurrence_rule_id, principal.id)
                task.recurrence_rule_id = None
                if rule is not None:
                    others = uow.recurrence_rules.count_tasks_referencing(rule.id, principal.id)
                    if others <= 1:  # only this task
                        rule.active = False
                        rule.next_occurrence = None
                        uow.recurrence_rules.save(rule)
            return

        if task.recurrence_rule_id is not None:
            # Update the existing rule in place; preserve series + counter.
            rule = uow.recurrence_rules.get_by_id(task.recurrence_rule_id, principal.id)
            if rule is None:
                raise NotFoundError("Recurrence rule not found for task")
            self._mutate_rule(rule, recurrence, task.due_date)
            rule.next_occurrence = plan_next(rule, task.due_date or rule.anchor_date).date
            uow.recurrence_rules.save(rule)
        else:
            # New series for a previously one-off task.
            rule = self._build_rule(recurrence, principal, now, anchor=task.due_date)
            uow.recurrence_rules.save(rule)
            series_id = task.series_id or self._ids.new_id()
            task.attach_to_series(series_id, rule.id, task.occurrence_number)
            rule.record_generation()
            rule.next_occurrence = plan_next(rule, task.due_date or rule.anchor_date).date
            uow.recurrence_rules.save(rule)

    def _build_rule(self, recurrence: RecurrenceInput, principal, now: datetime, *, anchor) -> RecurrenceRule:  # noqa: ANN001
        anchor_date = recurrence.anchor_date or anchor
        if anchor_date is None:
            anchor_date = self._clock.today(principal.timezone)
        return RecurrenceRule(
            id=self._ids.new_id(),
            owner_id=principal.id,
            name=recurrence.name,
            frequency=recurrence.frequency,
            interval=recurrence.interval,
            day_of_week=recurrence.day_of_week,
            anchor_date=anchor_date,
            end_type=recurrence.end_type,
            end_count=recurrence.end_count,
            end_date=recurrence.end_date,
            active=recurrence.active,
            created_at=now,
        )

    def _mutate_rule(self, rule: RecurrenceRule, recurrence: RecurrenceInput, new_due) -> None:  # noqa: ANN001
        """Re-anchor the rule on the current task due date when edited."""
        rule.name = recurrence.name
        rule.frequency = recurrence.frequency
        rule.interval = recurrence.interval
        rule.day_of_week = recurrence.day_of_week
        rule.end_type = recurrence.end_type
        rule.end_count = recurrence.end_count
        rule.end_date = recurrence.end_date
        rule.active = recurrence.active
        rule.anchor_date = recurrence.anchor_date or new_due or rule.anchor_date
        if rule.end_type is EndType.COUNT and rule.end_count is not None:
            # keep the counter coherent; never reduce below what was generated
            rule.end_count = max(rule.end_count, rule.occurrences_generated)
        rule.__post_init__()  # re-validate invariants after mutation

    # -- lifecycle -----------------------------------------------------
    def complete_task(self, principal, task_id: str) -> TaskDTO:
        self._authorize(principal, Permission.TASKS_COMPLETE)
        now = self._clock.now_utc()
        with self._database.create() as uow:
            settings = self._settings(uow, principal)
            task = uow.tasks.get_by_id(task_id, principal.id)
            if task is None:
                raise NotFoundError(f"Task {task_id} not found")

            transitioned = task.complete(now)  # idempotent
            successor = None
            if transitioned and task.recurrence_rule_id is not None:
                successor = self._generate_successor(uow, principal, task, now)

            uow.tasks.save(task)
            if successor is not None:
                uow.tasks.save(successor)
            uow.commit()

            return self._to_dto(
                task, uow, principal, today=self._clock.today(settings.timezone),
                warning_window=settings.warning_window_days,
            )

    def _generate_successor(self, uow, principal, task: Task, now: datetime) -> Task | None:  # noqa: ANN001
        """Create exactly one successor, or none if one already exists."""
        rule = uow.recurrence_rules.get_by_id(task.recurrence_rule_id, principal.id)
        if rule is None or not rule.active:
            return None

        # Guard: never create a duplicate open successor.
        existing_open = uow.tasks.find_open_by_recurrence_rule(rule.id, principal.id)
        if existing_open is not None and existing_open.id != task.id:
            return None

        after = task.due_date or rule.anchor_date
        plan = plan_next(rule, after, today=self._clock.today(principal.timezone))
        if plan.date is None:
            rule.active = False
            rule.next_occurrence = None
            uow.recurrence_rules.save(rule)
            return None

        rule.occurrences_generated += plan.skipped + 1
        rule.next_occurrence = plan.date
        uow.recurrence_rules.save(rule)

        successor = Task.create(
            id=self._ids.new_id(),
            owner_id=principal.id,
            title=task.title,
            category=task.category,
            now=now,
            priority=task.priority,
            description=task.description,
            due_date=plan.date,
            series_id=task.series_id,
            recurrence_rule_id=rule.id,
            occurrence_number=task.occurrence_number + 1,
        )
        task.record_event(
            SuccessorTaskCreated(
                task_id=successor.id,
                series_id=task.series_id or "",
                occurrence_number=successor.occurrence_number,
            )
        )
        return successor

    def reopen_task(self, principal, task_id: str) -> TaskDTO:
        self._authorize(principal, Permission.TASKS_REOPEN)
        now = self._clock.now_utc()
        with self._database.create() as uow:
            settings = self._settings(uow, principal)
            task = uow.tasks.get_by_id(task_id, principal.id)
            if task is None:
                raise NotFoundError(f"Task {task_id} not found")
            task.reopen(now)
            uow.tasks.save(task)
            uow.commit()
            return self._to_dto(
                task, uow, principal, today=self._clock.today(settings.timezone),
                warning_window=settings.warning_window_days,
            )

    def delete_task(self, principal, task_id: str) -> None:
        self._authorize(principal, Permission.TASKS_DELETE)
        with self._database.create() as uow:
            task = uow.tasks.get_by_id(task_id, principal.id)
            if task is None:
                raise NotFoundError(f"Task {task_id} not found")
            uow.tasks.delete(task_id, principal.id)
            uow.commit()

    # -- recurrence preview -------------------------------------------
    def preview_recurrence(self, principal, recurrence: RecurrenceInput, *, count: int = 5) -> list:

        self._authorize(principal, Permission.RECURRENCE_READ)
        now = self._clock.now_utc()
        rule = self._build_rule(recurrence, principal, now, anchor=recurrence.anchor_date)
        return preview_dates(rule, count=count, after_date=(rule.anchor_date if recurrence.anchor_date else None))
