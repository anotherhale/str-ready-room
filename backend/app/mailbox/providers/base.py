"""The mailbox provider port.

The application service depends only on this interface.  The IMAP adapter
implements it today; a Graph, Gmail API, or JMAP adapter would implement the same
two operations (list recent, read one) and be selected in the registry.

The port is deliberately **read-only**: there is no send/move/delete verb,
matching the product's "capture, don't correspond" scope.
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
    """Port: a read-only source of mail messages."""

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

    def health(self) -> bool:
        """Best-effort reachability probe.  Never raises."""
        try:
            self.list_messages(limit=1)
            return True
        except Exception:  # noqa: BLE001 - a probe must not raise
            return False
