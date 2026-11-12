// Calendar view: a read-through cache of the operator's external calendar.
//
// The backend is authoritative: it syncs the provider into a cache and derives
// which events fall inside the agenda window.  This view only renders what the
// server returned, offers an explicit Sync, and lets an event be captured into
// a responsibility (an idempotent server operation).
import { useMemo, useState } from "react";

import { CaptureToTaskDialog, type CaptureToTaskValues } from "../../components/CaptureToTaskDialog/CaptureToTaskDialog";
import { SectionPanel } from "../../components/SectionPanel/SectionPanel";
import { formatEventDay, formatEventTime, localDateOf } from "../../lib/dates";
import type {
  CalendarAgenda,
  CalendarCaptureInput,
  CalendarEvent,
  CalendarStatus,
  Category,
} from "../../types";

export interface CalendarViewProps {
  agenda: CalendarAgenda | null;
  status: CalendarStatus | null;
  categories: Category[];
  onSync: () => Promise<void>;
  onCapture: (event: CalendarEvent, input: CalendarCaptureInput) => Promise<void>;
  onCreate: (input: { summary: string; start: string; end: string }) => Promise<void>;
  busy: boolean;
}

function groupByDay(events: CalendarEvent[], timeZone: string): { day: string; events: CalendarEvent[] }[] {
  const groups = new Map<string, CalendarEvent[]>();
  for (const event of events) {
    const day = event.all_day ? event.start.slice(0, 10) : localDateOf(event.start, timeZone);
    const bucket = groups.get(day) ?? [];
    bucket.push(event);
    groups.set(day, bucket);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, dayEvents]) => ({
      day,
      events: dayEvents.sort((a, b) => a.start.localeCompare(b.start)),
    }));
}

export function CalendarView({ agenda, status, categories, onSync, onCapture, onCreate, busy }: CalendarViewProps) {
  const [capturing, setCapturing] = useState<CalendarEvent | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [summary, setSummary] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const groups = useMemo(
    () => (agenda ? groupByDay(agenda.events, agenda.timezone) : []),
    [agenda],
  );

  async function handleSync() {
    setSyncing(true);
    setMessage(null);
    setError(null);
    try {
      await onSync();
      setMessage("Calendar synced.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed.");
    } finally {
      setSyncing(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!summary.trim() || !start) {
      setError("A summary and start time are required.");
      return;
    }
    setError(null);
    try {
      await onCreate({ summary: summary.trim(), start, end: end || start });
      setSummary("");
      setStart("");
      setEnd("");
      setShowCreate(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create the event.");
    }
  }

  const unavailable = agenda !== null && !agenda.available;

  return (
    <div>
      <div className="panel-head">
        <span className="panel-title">
          Calendar
          {status?.provider && <span className="count">({status.provider})</span>}
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={() => setShowCreate((v) => !v)} disabled={unavailable}>
            {showCreate ? "Close" : "+ Event"}
          </button>
          <button className="btn primary" onClick={() => void handleSync()} disabled={busy || syncing || unavailable}>
            {syncing ? "Syncing…" : "Sync"}
          </button>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {message && <div className="toast-inline" role="status">{message}</div>}

      {unavailable ? (
        <section className="panel">
          <p className="panel-empty">
            Calendar integration is not available. {agenda?.detail ?? "Configure a provider to enable it."}
          </p>
        </section>
      ) : (
        <>
          {showCreate && (
            <form className="panel" onSubmit={handleCreate}>
              <div className="panel-head">
                <span className="panel-title">New event</span>
              </div>
              <div className="filters">
                <div className="field grow">
                  <label htmlFor="ev-summary">Summary</label>
                  <input
                    id="ev-summary"
                    type="text"
                    value={summary}
                    maxLength={300}
                    onChange={(e) => setSummary(e.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor="ev-start">Start</label>
                  <input
                    id="ev-start"
                    type="datetime-local"
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor="ev-end">End</label>
                  <input
                    id="ev-end"
                    type="datetime-local"
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                  />
                </div>
                <div className="field">
                  <label aria-hidden="true">&nbsp;</label>
                  <button className="btn primary" type="submit">
                    Create
                  </button>
                </div>
              </div>
            </form>
          )}

          {groups.length === 0 ? (
            <SectionPanel title="Upcoming" emptyText="No events in the agenda window.">
              {null}
            </SectionPanel>
          ) : (
            groups.map((group) => (
              <SectionPanel key={group.day} title={formatEventDay(group.day)} count={group.events.length}>
                {group.events.map((event) => (
                  <article key={event.id} className="event-row">
                    <div className="event-time">
                      {event.all_day ? "All day" : formatEventTime(event.start, agenda!.timezone)}
                    </div>
                    <div className="event-main">
                      <p className="task-title">{event.summary}</p>
                      <div className="task-meta">
                        {event.location && <span className="pill">{event.location}</span>}
                        {event.captured && <span className="badge ok">Captured</span>}
                      </div>
                    </div>
                    <div className="task-actions">
                      {event.captured ? (
                        <span className="badge ok">In inventory</span>
                      ) : (
                        <button className="btn btn-sm" disabled={busy} onClick={() => setCapturing(event)}>
                          Capture
                        </button>
                      )}
                    </div>
                  </article>
                ))}
              </SectionPanel>
            ))
          )}
        </>
      )}

      <CaptureToTaskDialog
        open={capturing !== null}
        defaultTitle={capturing?.summary ?? ""}
        defaultDueDate={
          capturing ? (capturing.all_day ? capturing.start.slice(0, 10) : localDateOf(capturing.start, agenda?.timezone ?? "UTC")) : undefined
        }
        categories={categories}
        onClose={() => setCapturing(null)}
        onSubmit={async (values: CaptureToTaskValues) => {
          if (!capturing) return;
          await onCapture(capturing, {
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
