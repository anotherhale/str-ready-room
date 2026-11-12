"""Unit tests for the mailbox domain (MIME parsing).

Pure: no database, no network, no IMAP.  The parsing is shared by every mail
backend, so it is tested once, directly.
"""
from __future__ import annotations

from email.message import EmailMessage as StdEmailMessage

from app.mailbox.domain import parse_message, summarize


def _raw(subject="Hello", sender="ops@detachment.demo", body="Body text") -> bytes:
    message = StdEmailMessage()
    message["From"] = sender
    message["To"] = "maverick@detachment.demo"
    message["Subject"] = subject
    message["Date"] = "Tue, 10 Mar 2026 13:00:00 +0000"
    message["Message-ID"] = "<msg-1@detachment.demo>"
    message.set_content(body)
    return message.as_bytes()


def test_parse_simple_plaintext_message():
    parsed = parse_message(_raw(body="Please sign the work order."), fallback_id="fallback")
    assert parsed.message_id == "<msg-1@detachment.demo>"
    assert parsed.sender == "ops@detachment.demo"
    assert parsed.subject == "Hello"
    assert parsed.body == "Please sign the work order."
    assert parsed.received_at is not None


def test_parse_uses_fallback_id_when_message_id_missing():
    message = StdEmailMessage()
    message["From"] = "a@b.c"
    message["Subject"] = "No id"
    message.set_content("hi")
    parsed = parse_message(message.as_bytes(), fallback_id="seq-7")
    assert parsed.message_id == "seq-7"


def test_parse_prefers_plaintext_over_html():
    message = StdEmailMessage()
    message["From"] = "a@b.c"
    message["Subject"] = "Both"
    message.set_content("plain body")
    message.add_alternative("<html><body><p>html body</p></body></html>", subtype="html")
    parsed = parse_message(message.as_bytes(), fallback_id="f")
    assert "plain body" in parsed.body


def test_parse_strips_html_when_only_html_present():
    message = StdEmailMessage()
    message["From"] = "a@b.c"
    message["Subject"] = "HTML only"
    message.set_content("<html><body><p>Rich <b>text</b></p></body></html>", subtype="html")
    parsed = parse_message(message.as_bytes(), fallback_id="f")
    assert "Rich" in parsed.body and "text" in parsed.body
    assert "<" not in parsed.body


def test_parse_ignores_attachments():
    message = StdEmailMessage()
    message["From"] = "a@b.c"
    message["Subject"] = "With attachment"
    message.set_content("see attached")
    message.add_attachment(b"binary", maintype="application", subtype="octet-stream", filename="x.bin")
    parsed = parse_message(message.as_bytes(), fallback_id="f")
    assert "see attached" in parsed.body
    assert "binary" not in parsed.body


def test_parse_decodes_encoded_subject():
    message = StdEmailMessage()
    message["From"] = "a@b.c"
    message["Subject"] = "=?utf-8?q?Caf=C3=A9_meeting?="
    message.set_content("hi")
    parsed = parse_message(message.as_bytes(), fallback_id="f")
    assert parsed.subject == "Café meeting"


def test_summarize_builds_snippet_without_full_body():
    summary = summarize(_raw(body="One two three four five six seven eight nine ten"), fallback_id="f")
    assert summary.message_id == "<msg-1@detachment.demo>"
    assert summary.snippet.startswith("One two three")
    assert len(summary.snippet) <= 120


def test_parse_handles_missing_date():
    message = StdEmailMessage()
    message["From"] = "a@b.c"
    message["Subject"] = "No date"
    message.set_content("hi")
    parsed = parse_message(message.as_bytes(), fallback_id="f")
    assert parsed.received_at is None
