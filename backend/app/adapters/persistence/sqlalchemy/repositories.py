"""SQLAlchemy repository implementations.

Repositories map rows to domain entities and back, scope every query by
``owner_id``, and never commit — the unit of work owns the transaction.  Driver
errors are translated into the application-owned ``PersistenceError``.
"""
from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ....application.ports.persistence import PersistenceError, TaskQuery
from ....calendar.entities import CalendarEventRecord
from ....domain.settings.entities import Category, OperatorSettings
from ....domain.tasks.entities import RecurrenceRule, Task
from ....domain.tasks.enums import TaskStatus
from ....domain.tasks.value_objects import category_key
from ....mailbox.entities import EmailSource
from .mappers import (
    apply_calendar_event_to_row,
    apply_email_source_to_row,
    apply_rule_to_row,
    apply_task_to_row,
    calendar_event_to_row,
    category_to_row,
    email_source_to_row,
    row_to_calendar_event,
    row_to_category,
    row_to_email_source,
    row_to_rule,
    row_to_settings,
    row_to_task,
    rule_to_row,
    settings_to_row,
    task_to_row,
)
from .models import (
    CalendarEventRow,
    CategoryRow,
    EmailSourceRow,
    RecurrenceRuleRow,
    SettingsRow,
    TaskRow,
)


class SqlAlchemyTaskRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, task_id: str, owner_id: str) -> Task | None:
        row = self._session.get(TaskRow, task_id)
        if row is None or row.owner_id != owner_id:
            return None
        return row_to_task(row)

    def list(self, criteria: TaskQuery, owner_id: str) -> list[Task]:
        stmt = select(TaskRow).where(TaskRow.owner_id == owner_id)
        if not criteria.include_all_statuses and criteria.status is not None:
            stmt = stmt.where(TaskRow.status == criteria.status.value)
        if criteria.category is not None:
            stmt = stmt.where(func.lower(TaskRow.category) == criteria.category.casefold())
        if criteria.search:
            like = f"%{criteria.search.casefold()}%"
            stmt = stmt.where(
                or_(
                    func.lower(TaskRow.title).like(like),
                    func.lower(func.coalesce(TaskRow.description, "")).like(like),
                )
            )
        if criteria.recurrence_rule_id is not None:
            stmt = stmt.where(TaskRow.recurrence_rule_id == criteria.recurrence_rule_id)

        stmt = stmt.order_by(
            TaskRow.status.desc(),        # 'open' sorts before 'completed' descending
            TaskRow.due_date.is_(None),   # dated tasks first
            TaskRow.due_date.asc(),
            TaskRow.created_at.asc(),
        )
        rows = self._session.execute(stmt).scalars().all()
        return [row_to_task(row) for row in rows]

    def save(self, task: Task) -> Task:
        try:
            row = self._session.get(TaskRow, task.id)
            if row is None:
                self._session.add(task_to_row(task))
            else:
                if row.owner_id != task.owner_id:
                    raise PersistenceError("cannot reassign task owner")
                apply_task_to_row(task, row)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError(f"failed to save task: {exc}") from exc
        return task

    def delete(self, task_id: str, owner_id: str) -> bool:
        row = self._session.get(TaskRow, task_id)
        if row is None or row.owner_id != owner_id:
            return False
        try:
            self._session.delete(row)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError(f"failed to delete task: {exc}") from exc
        return True

    def find_open_by_recurrence_rule(self, rule_id: str, owner_id: str) -> Task | None:
        stmt = (
            select(TaskRow)
            .where(
                TaskRow.owner_id == owner_id,
                TaskRow.recurrence_rule_id == rule_id,
                TaskRow.status == TaskStatus.OPEN.value,
            )
            .order_by(TaskRow.occurrence_number.asc())
            .limit(1)
        )
        row = self._session.execute(stmt).scalars().first()
        return row_to_task(row) if row is not None else None

    def count_by_series(self, series_id: str, owner_id: str) -> int:
        stmt = select(func.count()).select_from(TaskRow).where(
            TaskRow.owner_id == owner_id, TaskRow.series_id == series_id
        )
        return int(self._session.execute(stmt).scalar_one())

    def exists_any(self, owner_id: str) -> bool:
        stmt = select(func.count()).select_from(TaskRow).where(TaskRow.owner_id == owner_id)
        return int(self._session.execute(stmt).scalar_one()) > 0


class SqlAlchemyRecurrenceRuleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, rule_id: str, owner_id: str) -> RecurrenceRule | None:
        row = self._session.get(RecurrenceRuleRow, rule_id)
        if row is None or row.owner_id != owner_id:
            return None
        return row_to_rule(row)

    def save(self, rule: RecurrenceRule) -> RecurrenceRule:
        try:
            row = self._session.get(RecurrenceRuleRow, rule.id)
            if row is None:
                self._session.add(rule_to_row(rule))
            else:
                if row.owner_id != rule.owner_id:
                    raise PersistenceError("cannot reassign rule owner")
                apply_rule_to_row(rule, row)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError(f"failed to save recurrence rule: {exc}") from exc
        return rule

    def list_active(self, owner_id: str) -> list[RecurrenceRule]:
        stmt = (
            select(RecurrenceRuleRow)
            .where(RecurrenceRuleRow.owner_id == owner_id, RecurrenceRuleRow.active.is_(True))
            .order_by(RecurrenceRuleRow.created_at.asc())
        )
        return [row_to_rule(r) for r in self._session.execute(stmt).scalars().all()]

    def list_all(self, owner_id: str) -> list[RecurrenceRule]:
        stmt = (
            select(RecurrenceRuleRow)
            .where(RecurrenceRuleRow.owner_id == owner_id)
            .order_by(RecurrenceRuleRow.created_at.asc())
        )
        return [row_to_rule(r) for r in self._session.execute(stmt).scalars().all()]

    def count_tasks_referencing(self, rule_id: str, owner_id: str) -> int:
        stmt = select(func.count()).select_from(TaskRow).where(
            TaskRow.owner_id == owner_id, TaskRow.recurrence_rule_id == rule_id
        )
        return int(self._session.execute(stmt).scalar_one())

    def delete(self, rule_id: str, owner_id: str) -> bool:
        row = self._session.get(RecurrenceRuleRow, rule_id)
        if row is None or row.owner_id != owner_id:
            return False
        try:
            self._session.delete(row)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError(f"failed to delete recurrence rule: {exc}") from exc
        return True


class SqlAlchemySettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, owner_id: str) -> OperatorSettings | None:
        row = self._session.get(SettingsRow, owner_id)
        return row_to_settings(row) if row is not None else None

    def save(self, settings: OperatorSettings) -> OperatorSettings:
        try:
            row = self._session.get(SettingsRow, settings.owner_id)
            if row is None:
                self._session.add(settings_to_row(settings))
            else:
                row.warning_window_days = settings.warning_window_days
                row.timezone = settings.timezone
                row.seed_version = settings.seed_version
                row.calendar_seed_version = settings.calendar_seed_version
                row.email_seed_version = settings.email_seed_version
                row.updated_at = settings.updated_at
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError(f"failed to save settings: {exc}") from exc
        return settings


class SqlAlchemyCategoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, owner_id: str, *, include_inactive: bool = False) -> list[Category]:
        stmt = select(CategoryRow).where(CategoryRow.owner_id == owner_id)
        if not include_inactive:
            stmt = stmt.where(CategoryRow.active.is_(True))
        stmt = stmt.order_by(CategoryRow.created_at.asc(), CategoryRow.name.asc())
        return [row_to_category(r) for r in self._session.execute(stmt).scalars().all()]

    def get_by_id(self, category_id: str, owner_id: str) -> Category | None:
        row = self._session.get(CategoryRow, category_id)
        if row is None or row.owner_id != owner_id:
            return None
        return row_to_category(row)

    def find_by_name(self, name: str, owner_id: str) -> Category | None:
        target = category_key(name)
        for row in self._session.execute(
            select(CategoryRow).where(CategoryRow.owner_id == owner_id)
        ).scalars():
            if category_key(row.name) == target:
                return row_to_category(row)
        return None

    def save(self, category: Category) -> Category:
        try:
            row = self._session.get(CategoryRow, category.id)
            if row is None:
                self._session.add(category_to_row(category))
            else:
                row.name = category.name
                row.active = category.active
                row.is_default = category.is_default
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError(f"failed to save category: {exc}") from exc
        return category

    def delete(self, category_id: str, owner_id: str) -> bool:
        row = self._session.get(CategoryRow, category_id)
        if row is None or row.owner_id != owner_id:
            return False
        try:
            self._session.delete(row)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError(f"failed to delete category: {exc}") from exc
        return True

    def count(self, owner_id: str) -> int:
        stmt = select(func.count()).select_from(CategoryRow).where(CategoryRow.owner_id == owner_id)
        return int(self._session.execute(stmt).scalar_one())


class SqlAlchemyCalendarEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, event_id: str, owner_id: str) -> CalendarEventRecord | None:
        row = self._session.get(CalendarEventRow, event_id)
        if row is None or row.owner_id != owner_id:
            return None
        return row_to_calendar_event(row)

    def get_by_uid(self, uid: str, calendar_id: str, owner_id: str) -> CalendarEventRecord | None:
        stmt = select(CalendarEventRow).where(
            CalendarEventRow.owner_id == owner_id,
            CalendarEventRow.uid == uid,
            CalendarEventRow.calendar_id == calendar_id,
        )
        row = self._session.execute(stmt).scalars().first()
        return row_to_calendar_event(row) if row is not None else None

    def list(
        self, owner_id: str, *, start: date | None = None, end: date | None = None
    ) -> list[CalendarEventRecord]:
        stmt = select(CalendarEventRow).where(CalendarEventRow.owner_id == owner_id)
        if start is not None:
            stmt = stmt.where(CalendarEventRow.start >= datetime.combine(start, time.min))
        if end is not None:
            stmt = stmt.where(CalendarEventRow.start <= datetime.combine(end, time.max))
        stmt = stmt.order_by(CalendarEventRow.start.asc(), CalendarEventRow.summary.asc())
        return [row_to_calendar_event(r) for r in self._session.execute(stmt).scalars().all()]

    def save(self, record: CalendarEventRecord) -> CalendarEventRecord:
        try:
            row = self._session.get(CalendarEventRow, record.id)
            if row is None:
                self._session.add(calendar_event_to_row(record))
            else:
                if row.owner_id != record.owner_id:
                    raise PersistenceError("cannot reassign calendar event owner")
                apply_calendar_event_to_row(record, row)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError(f"failed to save calendar event: {exc}") from exc
        return record

    def delete(self, event_id: str, owner_id: str) -> bool:
        row = self._session.get(CalendarEventRow, event_id)
        if row is None or row.owner_id != owner_id:
            return False
        try:
            self._session.delete(row)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError(f"failed to delete calendar event: {exc}") from exc
        return True

    def delete_missing(self, calendar_id: str, keep_uids: set[str], owner_id: str) -> int:
        """Delete cached events in a calendar whose uid is no longer present."""
        stmt = select(CalendarEventRow).where(
            CalendarEventRow.owner_id == owner_id,
            CalendarEventRow.calendar_id == calendar_id,
        )
        removed = 0
        try:
            for row in self._session.execute(stmt).scalars().all():
                if row.uid not in keep_uids:
                    self._session.delete(row)
                    removed += 1
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError(f"failed to prune calendar events: {exc}") from exc
        return removed

    def count(self, owner_id: str) -> int:
        stmt = (
            select(func.count()).select_from(CalendarEventRow).where(CalendarEventRow.owner_id == owner_id)
        )
        return int(self._session.execute(stmt).scalar_one())


class SqlAlchemyEmailSourceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_message_id(self, message_id: str, owner_id: str) -> EmailSource | None:
        stmt = select(EmailSourceRow).where(
            EmailSourceRow.owner_id == owner_id, EmailSourceRow.message_id == message_id
        )
        row = self._session.execute(stmt).scalars().first()
        return row_to_email_source(row) if row is not None else None

    def list(self, owner_id: str) -> list[EmailSource]:
        stmt = (
            select(EmailSourceRow)
            .where(EmailSourceRow.owner_id == owner_id)
            .order_by(EmailSourceRow.captured_at.desc())
        )
        return [row_to_email_source(r) for r in self._session.execute(stmt).scalars().all()]

    def save(self, source: EmailSource) -> EmailSource:
        try:
            row = self._session.get(EmailSourceRow, source.id)
            if row is None:
                self._session.add(email_source_to_row(source))
            else:
                if row.owner_id != source.owner_id:
                    raise PersistenceError("cannot reassign email source owner")
                apply_email_source_to_row(source, row)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError(f"failed to save email source: {exc}") from exc
        return source

    def delete(self, source_id: str, owner_id: str) -> bool:
        row = self._session.get(EmailSourceRow, source_id)
        if row is None or row.owner_id != owner_id:
            return False
        try:
            self._session.delete(row)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError(f"failed to delete email source: {exc}") from exc
        return True

    def count(self, owner_id: str) -> int:
        stmt = select(func.count()).select_from(EmailSourceRow).where(EmailSourceRow.owner_id == owner_id)
        return int(self._session.execute(stmt).scalar_one())
