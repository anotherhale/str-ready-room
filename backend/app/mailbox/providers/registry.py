"""Mailbox provider factory.

The single place a concrete mailbox adapter is chosen from configuration.  A new
backend (Graph, Gmail API, JMAP) is added here and selected with
``READY_ROOM_EMAIL_PROVIDER`` without touching the domain, application services,
API, or UI (see DECISIONS D-033).
"""
from __future__ import annotations

from ...config import Settings
from .base import MailboxProvider
from .imap import ImapMailboxProvider

#: Providers that mean "mailbox integration is switched off".
DISABLED = {"", "none", "disabled", "off"}


def build_mailbox_provider(settings: Settings) -> MailboxProvider | None:
    """Return the configured provider, or ``None`` when disabled.

    The integration is optional: an unknown provider name is a configuration
    error, but a disabled one simply means the Mailbox view reports
    "unavailable" and the rest of READY ROOM is unaffected.
    """
    choice = (settings.email_provider or "").strip().lower()
    if choice in DISABLED:
        return None
    if choice == "imap":
        return ImapMailboxProvider(
            host=settings.imap_host,
            port=settings.imap_port,
            username=settings.imap_username,
            password=settings.imap_password,
            mailbox=settings.imap_mailbox,
        )
    raise ValueError(
        f"Unknown email provider {settings.email_provider!r}. Supported: imap, none."
    )
