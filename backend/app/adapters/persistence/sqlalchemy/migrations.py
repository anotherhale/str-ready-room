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
ADDITIVE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    # Populated as the schema evolves; kept empty for the first cut because the
    # initial create_all already contains every column.
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
