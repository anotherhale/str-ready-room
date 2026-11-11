"""Clock and id-generation ports.

The clock port is re-exported from the domain (it is a pure domain concept).
The id generator is an application port so ids can be deterministic in tests.
"""
from __future__ import annotations

from typing import Protocol

from ...domain.shared.clock import Clock  # re-exported for application use

__all__ = ["Clock", "IdGenerator"]


class IdGenerator(Protocol):
    """Generates opaque identifiers for new entities."""

    def new_id(self) -> str: ...
