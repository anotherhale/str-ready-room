// A small dialog that turns a calendar event or a mailbox message into a
// responsibility.  It collects only the fields the capture endpoints accept
// (title, category, priority, due date) and delegates the actual creation to
// the caller, which owns the idempotent capture call.
import { useEffect, useState } from "react";

import { PRIORITY_LABELS, PRIORITY_OPTIONS } from "../../lib/recurrence";
import type { Category, Priority } from "../../types";

export interface CaptureToTaskValues {
  title: string;
  category: string;
  priority: Priority;
  dueDate: string;
}

export interface CaptureToTaskDialogProps {
  open: boolean;
  /** The default title, pre-filled from the event/message. */
  defaultTitle: string;
  categories: Category[];
  /** A suggested due date (e.g. the event's local date). */
  defaultDueDate?: string;
  onClose: () => void;
  onSubmit: (values: CaptureToTaskValues) => Promise<void>;
}

export function CaptureToTaskDialog({
  open,
  defaultTitle,
  categories,
  defaultDueDate,
  onClose,
  onSubmit,
}: CaptureToTaskDialogProps) {
  const active = categories.filter((c) => c.active).map((c) => c.name);
  const [title, setTitle] = useState(defaultTitle);
  const [category, setCategory] = useState(active[0] ?? "General");
  const [priority, setPriority] = useState<Priority>("normal");
  const [dueDate, setDueDate] = useState(defaultDueDate ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setTitle(defaultTitle);
    setCategory(active[0] ?? "General");
    setPriority("normal");
    setDueDate(defaultDueDate ?? "");
    setError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, defaultTitle, defaultDueDate]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit({ title: title.trim(), category, priority, dueDate });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to capture.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="dialog-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog" role="dialog" aria-modal="true" aria-label="Capture as responsibility">
        <h2>Capture as responsibility</h2>
        {error && <div className="error-banner">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="cap-title">Title *</label>
            <input
              id="cap-title"
              type="text"
              value={title}
              maxLength={300}
              onChange={(e) => setTitle(e.target.value)}
              autoFocus
            />
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="cap-category">Category</label>
              <select id="cap-category" value={category} onChange={(e) => setCategory(e.target.value)}>
                {active.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="cap-priority">Priority</label>
              <select
                id="cap-priority"
                value={priority}
                onChange={(e) => setPriority(e.target.value as Priority)}
              >
                {PRIORITY_OPTIONS.map((p) => (
                  <option key={p} value={p}>
                    {PRIORITY_LABELS[p]}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label htmlFor="cap-due">Due date</label>
            <input
              id="cap-due"
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
            />
          </div>
          <div className="dialog-actions">
            <button className="btn ghost" type="button" onClick={onClose}>
              Cancel
            </button>
            <button className="btn primary" type="submit" disabled={saving}>
              {saving ? "Capturing…" : "Capture"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
