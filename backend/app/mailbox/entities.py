"""Mailbox cache entity: the provenance record for a captured message.

Capturing a message into a task writes one ``EmailSource`` row (message id,
sender, subject, received time, task id).  The row is what lets the UI mark a
message as "already captured" so it cannot silently spawn duplicates (see
DECISIONS D-026).

Recapture semantics: capturing an already-captured message **reuses the single
row** and re-points it at the newest task, rather than inserting a second row, so
"was this captured?" stays a single-row question.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class EmailSource:
    """A captured message and the task it became."""

    id: str
    owner_id: str
    message_id: str
    task_id: str | None = None
    sender: str | None = None
    subject: str | None = None
    received_at: datetime | None = None  # naive UTC
    captured_at: datetime | None = None  # naive UTC
