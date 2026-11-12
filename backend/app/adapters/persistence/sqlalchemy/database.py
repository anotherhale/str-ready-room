"""SQLAlchemy engine, session factory, and unit of work.

The engine is created from a configured URL, so the same adapter serves SQLite
and PostgreSQL.  The unit of work owns commit/rollback; repositories never
commit.  Driver/ORM exceptions are translated into application-owned
``PersistenceError``.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from ....application.ports.persistence import DatabasePort, PersistenceError
from .migrations import run_additive_migrations
from .models import Base
from .repositories import (
    SqlAlchemyCalendarEventRepository,
    SqlAlchemyCategoryRepository,
    SqlAlchemyEmailSourceRepository,
    SqlAlchemyRecurrenceRuleRepository,
    SqlAlchemySettingsRepository,
    SqlAlchemyTaskRepository,
)


def create_db_engine(database_url: str) -> Engine:
    """Create an engine tuned for the configured dialect."""
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        # SQLite needs cross-thread access off for FastAPI's threadpool.
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in database_url or database_url.endswith("sqlite://"):
            kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, **kwargs)

    if database_url.startswith("sqlite"):
        _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class SqlAlchemyUnitOfWork(DatabasePort):
    """A unit of work backed by one SQLAlchemy session."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._committed = False
        self._tasks: SqlAlchemyTaskRepository | None = None
        self._rules: SqlAlchemyRecurrenceRuleRepository | None = None
        self._settings: SqlAlchemySettingsRepository | None = None
        self._categories: SqlAlchemyCategoryRepository | None = None
        self._calendar_events: SqlAlchemyCalendarEventRepository | None = None
        self._email_sources: SqlAlchemyEmailSourceRepository | None = None

    # -- lifecycle -----------------------------------------------------
    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_factory()
        self._tasks = SqlAlchemyTaskRepository(self._session)
        self._rules = SqlAlchemyRecurrenceRuleRepository(self._session)
        self._settings = SqlAlchemySettingsRepository(self._session)
        self._categories = SqlAlchemyCategoryRepository(self._session)
        self._calendar_events = SqlAlchemyCalendarEventRepository(self._session)
        self._email_sources = SqlAlchemyEmailSourceRepository(self._session)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is not None:
                self.rollback()
            elif not self._committed:
                # A use case that did not explicitly commit is rolled back to
                # avoid accidental partial writes.
                self.rollback()
        finally:
            if self._session is not None:
                self._session.close()
            self._session = None
            self._committed = False

    # -- repositories --------------------------------------------------
    @property
    def tasks(self) -> SqlAlchemyTaskRepository:
        self._ensure()
        assert self._tasks is not None
        return self._tasks

    @property
    def recurrence_rules(self) -> SqlAlchemyRecurrenceRuleRepository:
        self._ensure()
        assert self._rules is not None
        return self._rules

    @property
    def settings(self) -> SqlAlchemySettingsRepository:
        self._ensure()
        assert self._settings is not None
        return self._settings

    @property
    def categories(self) -> SqlAlchemyCategoryRepository:
        self._ensure()
        assert self._categories is not None
        return self._categories

    @property
    def calendar_events(self) -> SqlAlchemyCalendarEventRepository:
        self._ensure()
        assert self._calendar_events is not None
        return self._calendar_events

    @property
    def email_sources(self) -> SqlAlchemyEmailSourceRepository:
        self._ensure()
        assert self._email_sources is not None
        return self._email_sources

    # -- transaction ---------------------------------------------------
    def commit(self) -> None:
        self._ensure()
        try:
            assert self._session is not None
            self._session.commit()
            self._committed = True
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            raise PersistenceError(f"commit failed: {exc}") from exc

    def rollback(self) -> None:
        if self._session is None:
            return
        self._session.rollback()

    def flush(self) -> None:
        self._ensure()
        try:
            assert self._session is not None
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError(f"flush failed: {exc}") from exc

    def _ensure(self) -> None:
        if self._session is None:
            raise PersistenceError("unit of work used outside its context manager")


class SqlAlchemyDatabaseFactory:
    """Creates units of work and initialises the schema."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_db_engine(database_url)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False, future=True)

    @property
    def engine(self) -> Engine:
        return self._engine

    def create(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)

    def init_schema(self) -> None:
        Base.metadata.create_all(self._engine)
        run_additive_migrations(self._engine)


@contextmanager
def unit_of_work(factory: SqlAlchemyDatabaseFactory) -> Iterator[SqlAlchemyUnitOfWork]:
    """Convenience context manager for one unit of work."""
    uow = factory.create()
    with uow as active:
        yield active
