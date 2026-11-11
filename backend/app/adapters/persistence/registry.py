"""Persistence adapter registry.

Selects the concrete database adapter from configuration.  Only this module (and
the composition root) knows which persistence technology is in use.
"""
from __future__ import annotations

from ...application.ports.persistence import DatabaseFactoryPort
from .sqlalchemy.database import SqlAlchemyDatabaseFactory


def build_database_factory(settings) -> DatabaseFactoryPort:  # noqa: ANN001 - config
    """Return the configured database factory."""
    adapter = settings.db_adapter
    if adapter == "sqlalchemy":
        return SqlAlchemyDatabaseFactory(settings.database_url)
    raise ValueError(f"Unknown database adapter: {adapter!r}")


__all__ = ["SqlAlchemyDatabaseFactory", "build_database_factory"]
