"""The in-memory mailbox double must honour the real adapter's purge contract."""

from __future__ import annotations

import pytest

from app.mailbox.providers.base import MailboxError
from tests.doubles import InMemoryMailboxProvider


def test_purge_empty_mailbox_returns_zero() -> None:
    mailbox = InMemoryMailboxProvider()

    assert mailbox.purge() == 0


def test_purge_removes_every_message_and_is_idempotent() -> None:
    mailbox = InMemoryMailboxProvider()
    mailbox.add(message_id="<one@detachment.demo>")
    mailbox.add(message_id="<two@detachment.demo>")

    assert mailbox.purge() == 2
    assert mailbox.purge() == 0
    assert mailbox.list_messages() == []


def test_purge_on_unreachable_mailbox_raises_502() -> None:
    mailbox = InMemoryMailboxProvider(reachable=False)

    with pytest.raises(MailboxError) as excinfo:
        mailbox.purge()

    assert excinfo.value.status == 502
