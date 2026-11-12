// Mailbox view: a read-only window onto the operator's inbox.
//
// The mailbox is deliberately read-only (no send/move/delete).  The one action
// that changes READY ROOM state is "Capture", which turns a message into a
// responsibility via an idempotent server call.
import { useState } from "react";

import { CaptureToTaskDialog, type CaptureToTaskValues } from "../../components/CaptureToTaskDialog/CaptureToTaskDialog";
import { formatEventTime } from "../../lib/dates";
import type { Category, EmailCaptureInput, EmailMessage, EmailSummary, MailboxStatus } from "../../types";

export interface MailboxViewProps {
  messages: EmailSummary[] | null;
  status: MailboxStatus | null;
  categories: Category[];
  timezone: string;
  /** The operator's local today (YYYY-MM-DD), server-resolved; seeds the capture dialog's due date. */
  today: string;
  onLoadMessage: (messageId: string) => Promise<EmailMessage>;
  onCapture: (messageId: string, input: EmailCaptureInput) => Promise<void>;
  busy: boolean;
}

export function MailboxView({
  messages,
  status,
  categories,
  timezone,
  today,
  onLoadMessage,
  onCapture,
  busy,
}: MailboxViewProps) {
  const [selected, setSelected] = useState<EmailMessage | null>(null);
  const [capturing, setCapturing] = useState<EmailSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const unavailable = status !== null && !status.available;

  // The message body is a one-shot load, but capture state is owned by the
  // refreshed ``messages`` list.  Reading it from the list (rather than from
  // the ``selected`` snapshot taken when the message was opened) keeps the
  // detail pane in step after a capture, so the Capture action is replaced by
  // "In inventory" immediately -- no reopen required.
  const selectedSummary = selected
    ? messages?.find((m) => m.message_id === selected.message_id) ?? null
    : null;
  const selectedCaptured = selectedSummary?.captured ?? selected?.captured ?? false;

  // Prefer the list entry; fall back to the loaded message so the dialog still
  // opens if the list has not caught up yet.
  function summaryFor(message: EmailMessage): EmailSummary {
    return {
      message_id: message.message_id,
      sender: message.sender,
      subject: message.subject,
      received_at: message.received_at,
      snippet: message.body.slice(0, 120),
      captured: message.captured,
      task_id: message.task_id,
    };
  }

  async function open(messageId: string) {
    setError(null);
    try {
      setSelected(await onLoadMessage(messageId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open the message.");
    }
  }

  return (
    <div>
      <div className="panel-head">
        <span className="panel-title">
          Mailbox
          {status?.mailbox && <span className="count">({status.mailbox})</span>}
        </span>
        {status && <span className="pill">{status.captured_count} captured</span>}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {unavailable ? (
        <section className="panel">
          <p className="panel-empty">
            Mailbox integration is not available. {status?.detail ?? "Configure a provider to enable it."}
          </p>
        </section>
      ) : (
        <div className="mail-layout">
          <section className="panel mail-list">
            <div className="panel-head">
              <span className="panel-title">Inbox</span>
            </div>
            {messages === null || messages.length === 0 ? (
              <p className="panel-empty">No messages.</p>
            ) : (
              messages.map((message) => (
                <button
                  key={message.message_id}
                  className={`mail-row ${selected?.message_id === message.message_id ? "active" : ""}`}
                  onClick={() => void open(message.message_id)}
                >
                  <div className="mail-row-head">
                    <span className="mail-subject">{message.subject || "(no subject)"}</span>
                    {message.captured && <span className="badge ok">Captured</span>}
                  </div>
                  <div className="task-meta">
                    <span>{message.sender}</span>
                    {message.received_at && (
                      <span>{formatEventTime(message.received_at, timezone)}</span>
                    )}
                  </div>
                  <p className="mail-snippet">{message.snippet}</p>
                </button>
              ))
            )}
          </section>

          <section className="panel mail-detail">
            {selected === null ? (
              <p className="panel-empty">Select a message to read it.</p>
            ) : (
              <>
                <div className="panel-head">
                  <span className="panel-title">{selected.subject || "(no subject)"}</span>
                  {selectedCaptured ? (
                    <span className="badge ok">In inventory</span>
                  ) : (
                    <button
                      className="btn primary btn-sm"
                      disabled={busy}
                      onClick={() => setCapturing(selectedSummary ?? summaryFor(selected))}
                    >
                      Capture
                    </button>
                  )}
                </div>
                <div className="task-meta" style={{ marginBottom: 8 }}>
                  <span>{selected.sender}</span>
                  {selected.received_at && <span>{formatEventTime(selected.received_at, timezone)}</span>}
                </div>
                <pre className="mail-body">{selected.body}</pre>
              </>
            )}
          </section>
        </div>
      )}

      <CaptureToTaskDialog
        open={capturing !== null}
        defaultTitle={capturing?.subject ?? ""}
        defaultDueDate={today}
        categories={categories}
        onClose={() => setCapturing(null)}
        onSubmit={async (values: CaptureToTaskValues) => {
          if (!capturing) return;
          await onCapture(capturing.message_id, {
            title: values.title,
            category: values.category,
            priority: values.priority,
            due_date: values.dueDate || null,
          });
        }}
      />
    </div>
  );
}
