"""Outbound mail port and SMTP adapter.

This is **not** part of the read-only ``MailboxProvider`` port.  It exists only
so the demo seeder and the ``scripts/demo-email.sh`` helper can deliver sample
mail *into* the demo mailbox (SMTP → GreenMail → IMAP).  The application request
path never sends mail (see DECISIONS D-026).
"""
from __future__ import annotations

import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage as StdEmailMessage


class MailSenderError(Exception):
    """A mail-delivery failure during seeding."""

    code = "mail_sender_error"


class MailSender(ABC):
    """Port: deliver a message to the demo mailbox."""

    @abstractmethod
    def send(self, *, sender: str, recipient: str, subject: str, body: str, message_id: str) -> None:
        """Deliver one plain-text message, with an explicit ``Message-ID``."""


class SmtpMailSender(MailSender):
    """SMTP adapter used by the seeder and the demo helper script.

    An explicit ``Message-ID`` is always set: the capture path looks messages up
    by ``HEADER Message-ID``, so a seeded message without one could not be found
    (see DECISIONS D-027).
    """

    def __init__(self, *, host: str, port: int, timeout: float = 10.0) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout

    def send(self, *, sender: str, recipient: str, subject: str, body: str, message_id: str) -> None:
        message = StdEmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject
        message["Message-ID"] = message_id
        message.set_content(body)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as client:
                client.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise MailSenderError(f"Could not deliver demo mail: {exc}") from exc
