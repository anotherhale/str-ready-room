import { useEffect, useMemo, useState } from "react";

import { formatShortDate } from "../../lib/dates";
import {
  END_TYPE_LABELS,
  FREQUENCY_LABELS,
  FREQUENCY_OPTIONS,
  PRIORITY_LABELS,
  PRIORITY_OPTIONS,
} from "../../lib/recurrence";
import { WEEKDAY_NAMES } from "../../lib/dates";
import { api, ApiError } from "../../services/apiClient";
import type { Category, EndType, Frequency, Priority, Task, TaskCreateInput } from "../../types";

export interface TaskDialogProps {
  open: boolean;
  task: Task | null;
  categories: Category[];
  defaultCategory?: string;
  onClose: () => void;
  onSubmit: (input: TaskCreateInput) => Promise<void>;
}

interface FormState {
  title: string;
  category: string;
  priority: Priority;
  description: string;
  dueDate: string;
  recurring: boolean;
  frequency: Frequency;
  interval: number;
  dayOfWeek: number | null;
  endType: EndType;
  endCount: number | null;
  endDate: string;
}

const EMPTY: FormState = {
  title: "",
  category: "",
  priority: "normal",
  description: "",
  dueDate: "",
  recurring: false,
  frequency: "weekly",
  interval: 1,
  dayOfWeek: null,
  endType: "never",
  endCount: null,
  endDate: "",
};

function fromTask(task: Task): FormState {
  const rule = task.recurrence;
  return {
    title: task.title,
    category: task.category,
    priority: task.priority,
    description: task.description ?? "",
    dueDate: task.due_date ?? "",
    recurring: rule !== null,
    frequency: rule?.frequency ?? "weekly",
    interval: rule?.interval ?? 1,
    dayOfWeek: rule?.day_of_week ?? null,
    endType: rule?.end_type ?? "never",
    // The embedded summary does not carry end_count/end_date; defaults keep the
    // field editable without inventing data.
    endCount: null,
    endDate: "",
  };
}

export function TaskDialog({
  open,
  task,
  categories,
  defaultCategory,
  onClose,
  onSubmit,
}: TaskDialogProps) {
  const activeCategories = useMemo(
    () => categories.filter((c) => c.active).map((c) => c.name),
    [categories],
  );
  const [form, setForm] = useState<FormState>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState<string[]>([]);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setPreview([]);
    setPreviewError(null);
    if (task) {
      setForm(fromTask(task));
    } else {
      setForm({
        ...EMPTY,
        category: defaultCategory ?? activeCategories[0] ?? "General",
      });
    }
  }, [open, task, defaultCategory, activeCategories]);

  // Server-authoritative recurrence preview.  The backend computes the dates;
  // the dialog only displays them.
  useEffect(() => {
    if (!open || !form.recurring) {
      setPreview([]);
      return;
    }
    let cancelled = false;
    const handle = window.setTimeout(async () => {
      try {
        const result = await api.previewRecurrence({
          name: form.title || "Preview",
          frequency: form.frequency,
          interval: form.interval,
          day_of_week: form.frequency === "weekly" ? form.dayOfWeek : null,
          anchor_date: form.dueDate || null,
          end_type: form.endType,
          end_count: form.endType === "count" ? form.endCount : null,
          end_date: form.endType === "on_date" ? form.endDate || null : null,
          count: 5,
        });
        if (!cancelled) {
          setPreview(result.dates);
          setPreviewError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setPreviewError(err instanceof ApiError ? err.message : "Preview unavailable.");
        }
      }
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [open, form]);

  if (!open) return null;

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim()) {
      setError("Title is required.");
      return;
    }
    if (!form.category.trim()) {
      setError("Category is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit({
        title: form.title.trim(),
        category: form.category,
        priority: form.priority,
        description: form.description.trim() ? form.description.trim() : null,
        due_date: form.dueDate || null,
        recurrence: form.recurring
          ? {
              name: form.title.trim(),
              frequency: form.frequency,
              interval: form.interval,
              day_of_week: form.frequency === "weekly" ? form.dayOfWeek : null,
              anchor_date: form.dueDate || null,
              end_type: form.endType,
              end_count: form.endType === "count" ? form.endCount : null,
              end_date: form.endType === "on_date" ? form.endDate || null : null,
              active: true,
            }
          : null,
      });
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save.");
    } finally {
      setSaving(false);
    }
  }

  const title = task ? "Edit responsibility" : "New responsibility";

  return (
    <div className="dialog-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog" role="dialog" aria-modal="true" aria-label={title}>
        <h2>{title}</h2>
        {error && <div className="error-banner">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="dlg-title">Title *</label>
            <input
              id="dlg-title"
              type="text"
              value={form.title}
              maxLength={300}
              onChange={(e) => update("title", e.target.value)}
              autoFocus
            />
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="dlg-category">Category</label>
              <select
                id="dlg-category"
                value={form.category}
                onChange={(e) => update("category", e.target.value)}
              >
                {activeCategories.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="dlg-priority">Priority</label>
              <select
                id="dlg-priority"
                value={form.priority}
                onChange={(e) => update("priority", e.target.value as Priority)}
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
            <label htmlFor="dlg-due">Due date</label>
            <input
              id="dlg-due"
              type="date"
              value={form.dueDate}
              onChange={(e) => update("dueDate", e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="dlg-desc">Notes</label>
            <textarea
              id="dlg-desc"
              value={form.description}
              maxLength={5000}
              onChange={(e) => update("description", e.target.value)}
            />
          </div>

          <fieldset>
            <legend>
              <label>
                <input
                  type="checkbox"
                  checked={form.recurring}
                  onChange={(e) => update("recurring", e.target.checked)}
                />{" "}
                Recurring
              </label>
            </legend>
            {form.recurring && (
              <>
                <div className="field-row">
                  <div className="field">
                    <label htmlFor="dlg-freq">Frequency</label>
                    <select
                      id="dlg-freq"
                      value={form.frequency}
                      onChange={(e) => update("frequency", e.target.value as Frequency)}
                    >
                      {FREQUENCY_OPTIONS.map((f) => (
                        <option key={f} value={f}>
                          {FREQUENCY_LABELS[f]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="dlg-interval">Every (interval)</label>
                    <input
                      id="dlg-interval"
                      type="number"
                      min={1}
                      max={365}
                      value={form.interval}
                      onChange={(e) => update("interval", Math.max(1, Number(e.target.value) || 1))}
                    />
                  </div>
                </div>
                {form.frequency === "weekly" && (
                  <div className="field">
                    <label htmlFor="dlg-dow">Weekday</label>
                    <select
                      id="dlg-dow"
                      value={form.dayOfWeek ?? ""}
                      onChange={(e) =>
                        update("dayOfWeek", e.target.value === "" ? null : Number(e.target.value))
                      }
                    >
                      <option value="">—</option>
                      {WEEKDAY_NAMES.map((name, index) => (
                        <option key={name} value={index}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                <div className="field">
                  <label htmlFor="dlg-end">Ends</label>
                  <select
                    id="dlg-end"
                    value={form.endType}
                    onChange={(e) => update("endType", e.target.value as EndType)}
                  >
                    {(Object.keys(END_TYPE_LABELS) as EndType[]).map((t) => (
                      <option key={t} value={t}>
                        {END_TYPE_LABELS[t]}
                      </option>
                    ))}
                  </select>
                </div>
                {form.endType === "count" && (
                  <div className="field">
                    <label htmlFor="dlg-endcount">Number of occurrences</label>
                    <input
                      id="dlg-endcount"
                      type="number"
                      min={1}
                      max={1000}
                      value={form.endCount ?? 1}
                      onChange={(e) => update("endCount", Math.max(1, Number(e.target.value) || 1))}
                    />
                  </div>
                )}
                {form.endType === "on_date" && (
                  <div className="field">
                    <label htmlFor="dlg-enddate">End date</label>
                    <input
                      id="dlg-enddate"
                      type="date"
                      value={form.endDate}
                      onChange={(e) => update("endDate", e.target.value)}
                    />
                  </div>
                )}
                <div>
                  <span className="hint" style={{ fontSize: 12, color: "var(--text-dim)" }}>
                    Next occurrences
                  </span>
                  {previewError ? (
                    <p className="panel-empty">{previewError}</p>
                  ) : (
                    <div className="preview-dates" aria-live="polite">
                      {preview.length === 0 ? (
                        <span className="panel-empty">—</span>
                      ) : (
                        preview.map((d) => (
                          <span key={d} className="pill">
                            {formatShortDate(d)}
                          </span>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </>
            )}
          </fieldset>

          <div className="dialog-actions">
            <button className="btn ghost" type="button" onClick={onClose}>
              Cancel
            </button>
            <button className="btn primary" type="submit" disabled={saving}>
              {saving ? "Saving…" : task ? "Save changes" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
