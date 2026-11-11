"""Identifier generation adapter.

``UuidIdGenerator`` is the production default.  ``SequentialIdGenerator`` is used
by tests that need deterministic, readable ids.
"""
from __future__ import annotations

import itertools
import uuid


class UuidIdGenerator:
    def new_id(self) -> str:
        return str(uuid.uuid4())


class SequentialIdGenerator:
    def __init__(self, prefix: str = "id") -> None:
        self._counter = itertools.count(1)
        self._prefix = prefix

    def new_id(self) -> str:
        return f"{self._prefix}-{next(self._counter):04d}"
