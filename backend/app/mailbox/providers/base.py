"""The mailbox provider port.

The application service depends only on this interface.  The IMAP adapter
implements it today; a Graph, Gmail API, or JMAP adapter would implement the same
operations and be selected in the registry.

The **operator-facing** operations are deliberately read-only: ``list_messages``
and ``get_message`` only, with no send/move/delete verb, matching the product's
"capture, don't correspond" scope (DECISIONS D-026).  ``purge`` is the single
exception and is **not** an operator capability: it exists solely so the demo
reset can return the demo mailbox to a clean state (DECISIONS D-040).  A
production adapter would either not implement it or gate it behind an admin
credential; it must never be reachable from an operator workflow.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ...domain.shared.errors import IntegrationError
from ..domain import EmailMessage, EmailSummary


class MailboxError(IntegrationError):
    """A mailbox provider failure, translated for the application layer.

    Inherits the domain ``IntegrationError`` so the single FastAPI error handler
    maps it (using its ``status`` hint) without importing this adapter.
    """

    code = "mailbox_error"


class MailboxProvider(ABC):
    """Port: a source of mail messages (read-only, plus a demo-only purge)."""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def list_messages(self, *, limit: int = 20) -> list[EmailSummary]:
        """Return the most recent messages, newest first."""

    @abstractmethod
    def get_message(self, message_id: str) -> EmailMessage:
        """Read one message by its ``Message-ID``.

        Implementations should also accept a ``seq-N`` reference as a fallback
        for messages that genuinely lack a ``Message-ID`` (see DECISIONS D-027).
        """

    @abstractmethod
    def purge(self) -> int:
        """Delete every message in the mailbox and return the count removed.

        **Demo reset only** — this is not part of the operator's read-only
        mailbox workflow.  Implementations must be best-effort and idempotent
        (an empty mailbox returns ``0``).
        """

    def health(self) -> bool:
        """Best-effort reachability probe.  Never raises."""
        try:
            self.list_messages(limit=1)
            return True
        except Exception:  # noqa: BLE001 - a probe must not raise
            return False
