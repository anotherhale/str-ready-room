"""The acting identity, independent of any web framework or vendor SDK.

Identity answers *who is acting*.  Authorization (see ``domain.authorization``)
answers *what that actor may do*.  The two are deliberately separate.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.errors import ValidationError


@dataclass(frozen=True)
class Principal:
    """A framework-independent representation of the current actor."""

    id: str
    display_name: str
    timezone: str
    roles: frozenset[str] = field(default_factory=frozenset)
    attributes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValidationError("Principal id is required")
        if not self.display_name:
            raise ValidationError("Principal display_name is required")
        if not self.timezone:
            raise ValidationError("Principal timezone is required")

    @property
    def first_name(self) -> str:
        return self.display_name.split(" ")[0]
