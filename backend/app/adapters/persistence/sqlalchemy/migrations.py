"""Safe additive schema evolution for the first cut.

We deliberately do **not** adopt Alembic at this size (see DECISIONS D-009).
This helper only *adds* missing columns; it is idempotent and never drops or
rewrites existing data.  A later Alembic adoption would live in this adapter and
preserve the same ports.
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

#: Columns added after the initial schema, expressed portably.  Each entry is
#: (table, column, column DDL used in a plain ALTER TABLE ADD COLUMN).
#:
#: ``calendar_events.task_id`` was introduced with the calendar→responsibility
#: capture feature (DECISIONS D-030).  ``create_all`` only creates missing
#: *tables*, never alters an existing one, so a database on a persistent volume
#: from before that feature needs this additive column or capture would fail.
ADDITIVE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("calendar_events", "task_id", "VARCHAR(36)"),
    ("operator_settings", "calendar_seed_version", "INTEGER NOT NULL DEFAULT 0"),
    ("operator_settings", "email_seed_version", "INTEGER NOT NULL DEFAULT 0"),
    #: The live "simulate an arrival" counter (DECISIONS D-039).
    ("operator_settings", "demo_arrival_seq", "INTEGER NOT NULL DEFAULT 0"),
)


def run_additive_migrations(engine: Engine) -> list[str]:
    """Add any missing columns.  Returns the list of applied changes."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    applied: list[str] = []

    for table, column, ddl in ADDITIVE_COLUMNS:
        if table not in existing_tables:
            continue
        columns = {col["name"] for col in inspector.get_columns(table)}
        if column in columns:
            continue
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        applied.append(f"{table}.{column}")

    return applied
