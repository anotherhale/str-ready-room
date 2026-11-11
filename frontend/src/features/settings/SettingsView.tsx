import { useEffect, useState } from "react";

import { formatShortDate } from "../../lib/dates";
import { FREQUENCY_LABELS, describeRecurrence } from "../../lib/recurrence";
import { WEEKDAY_NAMES } from "../../lib/dates";
import { api, ApiError } from "../../services/apiClient";
import type { Category, RecurrenceOverview, Settings } from "../../types";

export interface SettingsViewProps {
  settings: Settings;
  categories: Category[];
  recurrence: RecurrenceOverview | null;
  onSaved: () => Promise<void>;
  onReset: () => Promise<void>;
}

export function SettingsView({
  settings,
  categories,
  recurrence,
  onSaved,
  onReset,
}: SettingsViewProps) {
  const [warningWindow, setWarningWindow] = useState(settings.warning_window_days);
  const [timezone, setTimezone] = useState(settings.timezone);
  const [newCategory, setNewCategory] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setWarningWindow(settings.warning_window_days);
    setTimezone(settings.timezone);
  }, [settings]);

  function flash(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(null), 2500);
  }

  async function run(action: () => Promise<void>, message: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await onSaved();
      flash(message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {error && <div className="error-banner">{error}</div>}

      <div className="settings-grid">
        <section className="panel">
          <div className="panel-head">
            <span className="panel-title">Operational settings</span>
          </div>
          <div className="field">
            <label htmlFor="set-window">Warning window (days, 1–60)</label>
            <input
              id="set-window"
              type="number"
              min={1}
              max={60}
              value={warningWindow}
              onChange={(e) => setWarningWindow(Number(e.target.value) || 1)}
            />
            <span style={{ fontSize: 12, color: "var(--text-faint)" }}>
              Drives the Watch section and the dashboard label.
            </span>
          </div>
          <div className="field">
            <label htmlFor="set-tz">Operator timezone</label>
            <input
              id="set-tz"
              type="text"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            />
            <span style={{ fontSize: 12, color: "var(--text-faint)" }}>
              IANA identifier, e.g. America/New_York.
            </span>
          </div>
          <button
            className="btn primary"
            disabled={busy}
            onClick={() =>
              run(
                () =>
                  api
                    .updateSettings({ warning_window_days: warningWindow, timezone })
                    .then(() => undefined),
                "Settings saved.",
              )
            }
          >
            Save settings
          </button>
        </section>

        <section className="panel">
          <div className="panel-head">
            <span className="panel-title">Categories</span>
          </div>
          {categories.map((category) => (
            <div className="category-row" key={category.id}>
              <span className="name">
                {category.name}
                {category.is_default && (
                  <span className="pill" style={{ marginLeft: 8 }}>
                    default
                  </span>
                )}
                {!category.active && (
                  <span className="pill" style={{ marginLeft: 8 }}>
                    inactive
                  </span>
                )}
              </span>
              <button
                className="btn btn-sm ghost"
                disabled={busy}
                onClick={() =>
                  run(
                    () =>
                      api
                        .updateCategory(category.id, { active: !category.active })
                        .then(() => undefined),
                    category.active ? "Category deactivated." : "Category reactivated.",
                  )
                }
              >
                {category.active ? "Deactivate" : "Activate"}
              </button>
              <button
                className="btn btn-sm danger ghost"
                disabled={busy}
                onClick={() =>
                  run(() => api.deleteCategory(category.id).then(() => undefined), "Category removed.")
                }
              >
                Delete
              </button>
            </div>
          ))}
          <div className="field" style={{ marginTop: 12 }}>
            <label htmlFor="new-category">Add category</label>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                id="new-category"
                type="text"
                value={newCategory}
                maxLength={80}
                placeholder="e.g. Flight Admin"
                onChange={(e) => setNewCategory(e.target.value)}
              />
              <button
                className="btn"
                disabled={busy || !newCategory.trim()}
                onClick={() =>
                  run(async () => {
                    await api.createCategory(newCategory.trim());
                    setNewCategory("");
                  }, "Category added.")
                }
              >
                Add
              </button>
            </div>
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="panel-head">
          <span className="panel-title">
            Recurrence overview
            {recurrence && <span className="count">({recurrence.rules.length})</span>}
          </span>
        </div>
        {!recurrence || recurrence.rules.length === 0 ? (
          <p className="panel-empty">No recurring responsibilities defined.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", color: "var(--text-faint)", fontSize: 12 }}>
                <th style={{ padding: "4px 8px" }}>Name</th>
                <th style={{ padding: "4px 8px" }}>Cadence</th>
                <th style={{ padding: "4px 8px" }}>Generated</th>
                <th style={{ padding: "4px 8px" }}>Next</th>
                <th style={{ padding: "4px 8px" }}>State</th>
              </tr>
            </thead>
            <tbody>
              {recurrence.rules.map((rule) => (
                <tr key={rule.rule_id} style={{ borderTop: "1px solid var(--line)" }}>
                  <td style={{ padding: "6px 8px" }}>{rule.name}</td>
                  <td style={{ padding: "6px 8px" }}>
                    {describeRecurrence(
                      rule.frequency,
                      rule.interval,
                      rule.day_of_week,
                      WEEKDAY_NAMES,
                    )}{" "}
                    <span style={{ color: "var(--text-faint)", fontSize: 12 }}>
                      ({FREQUENCY_LABELS[rule.frequency]})
                    </span>
                  </td>
                  <td style={{ padding: "6px 8px" }}>{rule.occurrences_generated}</td>
                  <td style={{ padding: "6px 8px" }}>
                    {rule.next_occurrence ? formatShortDate(rule.next_occurrence) : "—"}
                  </td>
                  <td style={{ padding: "6px 8px" }}>
                    <span className={`badge ${rule.active ? "ok" : "neutral"}`}>
                      {rule.active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <span className="panel-title">Demonstration data</span>
        </div>
        <p style={{ color: "var(--text-dim)", marginTop: 0 }}>
          Reset clears all responsibilities and recurrence rules, then restores the default
          categories and settings. Use this to return to the demonstration state.
        </p>
        <button
          className="btn danger"
          disabled={busy}
          onClick={() => {
            if (window.confirm("Reset all demonstration data? This cannot be undone.")) {
              void run(onReset, "Demonstration data reset.");
            }
          }}
        >
          Reset demo data
        </button>
      </section>

      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}
