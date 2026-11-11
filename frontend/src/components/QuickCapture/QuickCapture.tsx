import { useEffect, useState } from "react";

import { PRIORITY_LABELS, PRIORITY_OPTIONS } from "../../lib/recurrence";
import type { Priority, TaskCreateInput } from "../../types";

export interface QuickCaptureProps {
  categories: string[];
  onSubmit: (input: TaskCreateInput) => Promise<void> | void;
  onOpenFull: () => void;
  busy?: boolean;
}

// Local calendar date as YYYY-MM-DD. Deliberately computed from the browser
// clock only as a *default*; the backend remains authoritative for "today".
function todayIso(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

// Minimal-friction capture: a title plus three compact, pre-defaulted controls
// (category, due date, priority) so a responsibility can be recorded in one
// pass. The full dialog is one click away for anything more.
export function QuickCapture({ categories, onSubmit, onOpenFull, busy }: QuickCaptureProps) {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState(categories[0] ?? "General");
  const [dueDate, setDueDate] = useState(todayIso());
  const [priority, setPriority] = useState<Priority>("normal");

  // Keep the selected category valid if the configured list changes (e.g. the
  // operator adds/removes categories in Settings).
  useEffect(() => {
    if (categories.length > 0 && !categories.includes(category)) {
      setCategory(categories[0]);
    }
  }, [categories, category]);

  async function submit() {
    const trimmed = title.trim();
    if (!trimmed) return;
    await onSubmit({
      title: trimmed,
      category,
      priority,
      due_date: dueDate || null,
    });
    setTitle("");
    setPriority("normal");
    setDueDate(todayIso());
  }

  return (
    <form
      className="quick-capture"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
      aria-label="Quick capture"
    >
      <label htmlFor="quick-capture-input" className="hint">
        Quick capture
      </label>
      <input
        id="quick-capture-input"
        type="text"
        placeholder="Capture a responsibility…"
        value={title}
        maxLength={300}
        onChange={(e) => setTitle(e.target.value)}
      />
      <select
        aria-label="Category"
        value={category}
        onChange={(e) => setCategory(e.target.value)}
      >
        {categories.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
      <input
        type="date"
        aria-label="Due date"
        value={dueDate}
        onChange={(e) => setDueDate(e.target.value)}
      />
      <select
        aria-label="Priority"
        value={priority}
        onChange={(e) => setPriority(e.target.value as Priority)}
      >
        {PRIORITY_OPTIONS.map((p) => (
          <option key={p} value={p}>
            {PRIORITY_LABELS[p]}
          </option>
        ))}
      </select>
      <button className="btn primary" type="submit" disabled={busy || !title.trim()}>
        Capture
      </button>
      <button className="btn" type="button" onClick={onOpenFull}>
        + New
      </button>
    </form>
  );
}
