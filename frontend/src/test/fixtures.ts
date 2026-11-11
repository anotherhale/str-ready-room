import type { Briefing, Category, Dashboard, Settings, Task } from "../types";

export function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "t1",
    owner_id: "maverick",
    title: "Prepare Monday morning detachment brief",
    description: null,
    category: "Detachment Operations",
    status: "open",
    priority: "normal",
    due_date: "2026-03-10",
    created_at: "2026-03-01T12:00:00",
    updated_at: "2026-03-01T12:00:00",
    completed_at: null,
    series_id: null,
    occurrence_number: 1,
    recurrence: null,
    urgency: "due",
    days_until_due: 0,
    ...overrides,
  };
}

export function makeDashboard(overrides: Partial<Dashboard> = {}): Dashboard {
  return {
    today: "2026-03-10",
    timezone: "America/New_York",
    greeting_name: "Maverick",
    warning_window_days: 3,
    watch_label: "3-Day Watch",
    readiness_summary: "2 responsibilities require attention today.",
    counts: { overdue: 1, due: 1, watch: 1, horizon: 2, completed_this_week: 3 },
    today_tasks: [],
    watch_tasks: [],
    horizon_tasks: [],
    ...overrides,
  };
}

export function makeBriefing(overrides: Partial<Briefing> = {}): Briefing {
  return {
    date: "2026-03-10",
    timezone: "America/New_York",
    today: [],
    upcoming: [],
    overdue: [],
    recurring_obligations: [],
    look_ahead: "Quiet week ahead.",
    ...overrides,
  };
}

export function makeCategory(name: string, overrides: Partial<Category> = {}): Category {
  return { id: name.toLowerCase().replace(/\s+/g, "-"), name, active: true, is_default: false, ...overrides };
}

export function makeSettings(overrides: Partial<Settings> = {}): Settings {
  return {
    warning_window_days: 3,
    timezone: "America/New_York",
    categories: [
      makeCategory("Flight Administration", { is_default: true }),
      makeCategory("Maintenance", { is_default: true }),
      makeCategory("General", { is_default: true }),
    ],
    ...overrides,
  };
}
