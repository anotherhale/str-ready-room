import { useState } from "react";

import { QuickCapture } from "../components/QuickCapture/QuickCapture";
import { TaskDialog } from "../components/TaskDialog/TaskDialog";
import { BriefingView } from "../features/briefing/BriefingView";
import { CalendarView } from "../features/calendar/CalendarView";
import { DashboardView } from "../features/dashboard/DashboardView";
import { MailboxView } from "../features/mailbox/MailboxView";
import { SettingsView } from "../features/settings/SettingsView";
import { InventoryView } from "../features/tasks/InventoryView";
import { api, ApiError } from "../services/apiClient";
import { useAppData } from "../services/useAppData";
import type { CalendarCaptureInput, EmailCaptureInput, Task, TaskCreateInput } from "../types";

type View = "dashboard" | "inventory" | "calendar" | "mailbox" | "briefing" | "settings";

const NAV: { id: View; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "inventory", label: "Inventory" },
  { id: "calendar", label: "Calendar" },
  { id: "mailbox", label: "Mailbox" },
  { id: "briefing", label: "Briefing" },
  { id: "settings", label: "Settings" },
];

export function App() {
  const { data, loading, error, filters, setFilters, refresh, refreshCalendar, refreshMailbox, mutate } =
    useAppData();
  const [view, setView] = useState<View>("dashboard");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  function flash(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(null), 2500);
  }

  function handleError(err: unknown) {
    flash(err instanceof ApiError ? err.message : "Something went wrong.");
  }

  async function guard(action: () => Promise<unknown>) {
    setBusy(true);
    try {
      await mutate(action);
    } catch (err) {
      handleError(err);
    } finally {
      setBusy(false);
    }
  }

  async function handleQuickCapture(input: TaskCreateInput) {
    try {
      await mutate(() => api.createTask(input));
      flash("Captured.");
    } catch (err) {
      handleError(err);
    }
  }

  function openNew() {
    setEditing(null);
    setDialogOpen(true);
  }

  function openEdit(task: Task) {
    setEditing(task);
    setDialogOpen(true);
  }

  async function handleDialogSubmit(input: TaskCreateInput) {
    if (editing) {
      await mutate(() =>
        api.updateTask(editing.id, {
          title: input.title,
          category: input.category,
          priority: input.priority,
          description: input.description ?? null,
          description_set: true,
          due_date: input.due_date ?? null,
          due_date_set: true,
          recurrence: input.recurrence ?? null,
          recurrence_set: true,
        }),
      );
    } else {
      await mutate(() => api.createTask(input));
    }
  }

  const categories = (data.settings?.categories ?? [])
    .filter((c) => c.active)
    .map((c) => c.name);

  if (loading && !data.dashboard) {
    return <div className="status">Loading READY ROOM…</div>;
  }

  if (!data.dashboard || !data.settings) {
    return (
      <div className="status">
        <p>{error ?? "Unable to load READY ROOM."}</p>
        <button className="btn primary" onClick={() => void refresh()}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          READY ROOM <small>detachment ops</small>
        </div>
        <nav className="nav" aria-label="Primary">
          {NAV.map((item) => (
            <button
              key={item.id}
              aria-current={view === item.id ? "page" : undefined}
              onClick={() => setView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="header-spacer" />
      </header>

      <QuickCapture
        categories={categories}
        onSubmit={handleQuickCapture}
        onOpenFull={openNew}
        busy={busy}
      />

      <main className="app-main">
        {error && (
          <div className="error-banner">
            <span>{error}</span>
            <button className="btn btn-sm" onClick={() => void refresh()}>
              Retry
            </button>
          </div>
        )}

        {view === "dashboard" && (
          <DashboardView
            dashboard={data.dashboard}
            onEdit={openEdit}
            onComplete={(t) => void guard(() => api.completeTask(t.id))}
            onReopen={(t) => void guard(() => api.reopenTask(t.id))}
            onOpenBriefing={() => setView("briefing")}
            onOpenInventory={() => setView("inventory")}
            busy={busy}
          />
        )}

        {view === "inventory" && (
          <InventoryView
            tasks={data.tasks}
            total={data.tasks.length}
            categories={categories}
            filters={filters}
            onFiltersChange={setFilters}
            onEdit={openEdit}
            onComplete={(t) => void guard(() => api.completeTask(t.id))}
            onReopen={(t) => void guard(() => api.reopenTask(t.id))}
            onDelete={(t) => {
              if (window.confirm(`Delete "${t.title}"?`)) {
                void guard(() => api.deleteTask(t.id));
              }
            }}
            onNew={openNew}
            busy={busy}
          />
        )}

        {view === "briefing" && data.briefing && <BriefingView briefing={data.briefing} />}

        {view === "calendar" && (
          <CalendarView
            agenda={data.calendar}
            status={data.calendarStatus}
            categories={data.settings.categories}
            busy={busy}
            onSync={async () => {
              await api.syncCalendar();
              await refreshCalendar();
              await refresh();
            }}
            onCreate={async (input) => {
              await api.createCalendarEvent(input);
              await refreshCalendar();
            }}
            onCapture={async (event, input: CalendarCaptureInput) => {
              await mutate(() => api.captureCalendarEvent(event.id, input));
              await refreshCalendar();
              flash("Captured to inventory.");
            }}
          />
        )}

        {view === "mailbox" && (
          <MailboxView
            messages={data.mailbox}
            status={data.mailboxStatus}
            categories={data.settings.categories}
            timezone={data.settings.timezone}
            busy={busy}
            onLoadMessage={(id) => api.getMessage(id)}
            onCapture={async (messageId, input: EmailCaptureInput) => {
              await mutate(() => api.captureMessage(messageId, input));
              await refreshMailbox();
              flash("Captured to inventory.");
            }}
          />
        )}

        {view === "settings" && (
          <SettingsView
            settings={data.settings}
            categories={data.settings.categories}
            recurrence={data.recurrence}
            onSaved={refresh}
            onReset={async () => {
              await api.resetDemo();
            }}
          />
        )}
      </main>

      <TaskDialog
        open={dialogOpen}
        task={editing}
        categories={data.settings.categories}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleDialogSubmit}
      />

      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}
