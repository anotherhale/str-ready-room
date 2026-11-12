"""Provider-independent mailbox domain: message value objects and MIME parsing.

MIME is the interchange format every mail backend (IMAP, JMAP, a Graph adapter)
ultimately hands back, so the parsing lives here rather than in one adapter.  An
adapter that returns raw bytes reuses :func:`parse_message` unchanged.

This module imports only the standard library — no ``imaplib``, no HTTP, no ORM.
"""
from __future__ import annotations

import email
from dataclasses import dataclass
from datetime import UTC, datetime
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime

#: Bound the body we keep on a task so a huge message cannot bloat the row.
MAX_BODY_CHARS = 4000


@dataclass(frozen=True)
class EmailSummary:
    """Lightweight listing entry — enough to render a mailbox row."""

    message_id: str
    sender: str
    subject: str
    received_at: datetime | None
    snippet: str


@dataclass(frozen=True)
class EmailMessage:
    """A fully read message."""

    message_id: str
    sender: str
    subject: str
    received_at: datetime | None
    body: str


def parse_message(raw: bytes | str, *, fallback_id: str) -> EmailMessage:
    """Parse a raw RFC 822 message into a provider-independent value object.

    ``fallback_id`` is used when the message carries no ``Message-ID`` header
    (GreenMail seeds and some relays omit it), so every message still has a
    stable identity.
    """
    if isinstance(raw, str):
        raw = raw.encode("utf-8", "replace")
    message: Message = email.message_from_bytes(raw)

    message_id = (message.get("Message-ID") or "").strip() or fallback_id
    sender = _decode_header(message.get("From", "")) or "(unknown sender)"
    subject = _decode_header(message.get("Subject", "")) or "(no subject)"
    received_at = _parse_date(message.get("Date"))

    return EmailMessage(
        message_id=message_id,
        sender=sender,
        subject=subject,
        received_at=received_at,
        body=extract_body(message),
    )


def extract_body(message: Message) -> str:
    """Return a plain-text rendering of the message body (bounded).

    Prefers ``text/plain``; falls back to stripping tags from ``text/html`` so a
    newsletter-style message still yields readable text.
    """
    plain: str | None = None
    html: str | None = None

    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            disposition = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            content_type = part.get_content_type()
            payload = _decode_payload(part)
            if content_type == "text/plain" and plain is None:
                plain = payload
            elif content_type == "text/html" and html is None:
                html = payload
    else:
        payload = _decode_payload(message)
        if message.get_content_type() == "text/html":
            html = payload
        else:
            plain = payload

    text = plain if plain is not None else _strip_html(html or "")
    return text.strip()[:MAX_BODY_CHARS]


def summarize(raw: bytes | str, *, fallback_id: str, snippet_chars: int = 120) -> EmailSummary:
    """Build a listing entry without keeping the whole body."""
    parsed = parse_message(raw, fallback_id=fallback_id)
    snippet = " ".join(parsed.body.split())[:snippet_chars]
    return EmailSummary(
        message_id=parsed.message_id,
        sender=parsed.sender,
        subject=parsed.subject,
        received_at=parsed.received_at,
        snippet=snippet,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _decode_payload(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if not isinstance(payload, (bytes, bytearray)):
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return bytes(payload).decode(charset, "replace")
    except (LookupError, UnicodeDecodeError):
        return bytes(payload).decode("utf-8", "replace")


def _decode_header(value: str) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:  # noqa: BLE001 - a malformed header must not break listing
        return value.strip()


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC).replace(tzinfo=None)
    return parsed.astimezone(UTC).replace(tzinfo=None)


def _strip_html(value: str) -> str:
    import re

    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
    )
    return " ".join(text.split())
