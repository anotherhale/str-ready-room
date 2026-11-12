"""IMAP adapter for a self-hosted GreenMail server.

Every ``imaplib`` call lives here; the rest of the application sees only the
``MailboxProvider`` port and provider-independent value objects.  The adapter is
read-only (``SELECT``/``SEARCH``/``FETCH``) and uses ``BODY.PEEK`` so listing the
mailbox never marks a message as read.

Two GreenMail realities shape this code (see DECISIONS D-027):

* the mailbox is addressed by its **full** address (``maverick@detachment.demo``),
  not the local part — logging in as the local part would create a *different*
  mailbox;
* a message is looked up by ``HEADER Message-ID``, with a ``seq-N`` sequence
  number as a fallback for messages that genuinely lack a ``Message-ID``.
"""
from __future__ import annotations

import imaplib
from collections.abc import Iterator
from contextlib import contextmanager, suppress

from ..domain import EmailMessage, EmailSummary, parse_message, summarize
from .base import MailboxError, MailboxProvider

#: A ``get_message`` reference of the form ``seq-12`` means "IMAP sequence 12".
_SEQ_PREFIX = "seq-"


class ImapMailboxProvider(MailboxProvider):
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        mailbox: str = "INBOX",
        timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._mailbox = mailbox
        self._timeout = timeout

    # -- port ----------------------------------------------------------
    def list_messages(self, *, limit: int = 20) -> list[EmailSummary]:
        with self._connected() as client:
            uids = self._all_sequence_numbers(client)
            if not uids:
                return []
            recent = uids[-limit:][::-1]  # newest first
            summaries: list[EmailSummary] = []
            for seq in recent:
                raw = self._fetch_raw(client, seq)
                if raw is None:
                    continue
                summaries.append(summarize(raw, fallback_id=f"{_SEQ_PREFIX}{seq}"))
            return summaries

    def get_message(self, message_id: str) -> EmailMessage:
        with self._connected() as client:
            seq = self._resolve_sequence(client, message_id)
            raw = self._fetch_raw(client, seq)
            if raw is None:
                raise MailboxError(f"Message {message_id!r} could not be read", status=404, code="not_found")
            return parse_message(raw, fallback_id=message_id)

    # -- internals -----------------------------------------------------
    @contextmanager
    def _connected(self) -> Iterator[imaplib.IMAP4]:
        try:
            client = imaplib.IMAP4(self._host, self._port, timeout=self._timeout)
        except (OSError, imaplib.IMAP4.error) as exc:
            raise MailboxError(f"Mailbox unreachable: {exc}", status=502) from exc
        try:
            client.login(self._username, self._password)
            client.select(self._mailbox, readonly=True)
        except imaplib.IMAP4.error as exc:
            raise MailboxError(f"Mailbox login/select failed: {exc}", status=502) from exc
        try:
            yield client
        finally:
            with suppress(imaplib.IMAP4.error):
                client.close()
            with suppress(imaplib.IMAP4.error, OSError):
                client.logout()

    @staticmethod
    def _all_sequence_numbers(client: imaplib.IMAP4) -> list[int]:
        status, data = client.search(None, "ALL")
        if status != "OK" or not data or not data[0]:
            return []
        return [int(part) for part in data[0].split()]

    @staticmethod
    def _fetch_raw(client: imaplib.IMAP4, seq: int) -> bytes | None:
        # BODY.PEEK avoids setting \Seen just by reading.
        status, data = client.fetch(str(seq), "(BODY.PEEK[])")
        if status != "OK" or not data:
            return None
        for item in data:
            if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
                return bytes(item[1])
        return None

    def _resolve_sequence(self, client: imaplib.IMAP4, message_id: str) -> int:
        if message_id.startswith(_SEQ_PREFIX):
            try:
                return int(message_id[len(_SEQ_PREFIX) :])
            except ValueError as exc:
                raise MailboxError(f"Invalid message reference {message_id!r}", status=400) from exc

        for candidate in _message_id_candidates(message_id):
            status, data = client.search(None, "HEADER", "Message-ID", candidate)
            if status == "OK" and data and data[0]:
                numbers = [int(part) for part in data[0].split()]
                if numbers:
                    return numbers[-1]
        raise MailboxError(f"Message {message_id!r} not found", status=404, code="not_found")


def _message_id_candidates(message_id: str) -> list[str]:
    """Try the id as given, then bracketed/unbracketed variants."""
    candidates = [message_id]
    stripped = message_id.strip("<>")
    if stripped != message_id:
        candidates.append(stripped)
    else:
        candidates.append(f"<{stripped}>")
    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique
