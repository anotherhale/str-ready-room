import type {
  Briefing,
  CalendarAgenda,
  CalendarEvent,
  CalendarStatus,
  Category,
  Dashboard,
  EmailMessage,
  EmailSummary,
  MailboxStatus,
  Settings,
  Task,
} from "../types";

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

export function makeCalendarEvent(overrides: Partial<CalendarEvent> = {}): CalendarEvent {
  return {
    id: "ev1",
    uid: "uid-1",
    calendar_id: "/detachment/",
    summary: "Detachment flight quarters",
    start: "2026-03-10T07:30:00-04:00",
    end: "2026-03-10T08:15:00-04:00",
    all_day: false,
    location: "Ready room",
    description: null,
    task_id: null,
    captured: false,
    ...overrides,
  };
}

export function makeCalendarAgenda(overrides: Partial<CalendarAgenda> = {}): CalendarAgenda {
  return {
    date: "2026-03-10",
    timezone: "America/New_York",
    window_days: 7,
    available: true,
    events: [],
    detail: null,
    ...overrides,
  };
}

export function makeCalendarStatus(overrides: Partial<CalendarStatus> = {}): CalendarStatus {
  return {
    available: true,
    provider: "caldav",
    calendar_id: "detachment",
    cached_events: 0,
    last_synced_at: "2026-03-10T13:00:00",
    detail: null,
    ...overrides,
  };
}

export function makeEmailSummary(overrides: Partial<EmailSummary> = {}): EmailSummary {
  return {
    message_id: "<m1@x>",
    sender: "ops@detachment.demo",
    subject: "Tow bar inspection",
    received_at: "2026-03-10T13:00:00",
    snippet: "Confirm the window with the machine shop.",
    captured: false,
    task_id: null,
    ...overrides,
  };
}

export function makeEmailMessage(overrides: Partial<EmailMessage> = {}): EmailMessage {
  return {
    message_id: "<m1@x>",
    sender: "ops@detachment.demo",
    subject: "Tow bar inspection",
    received_at: "2026-03-10T13:00:00",
    body: "Full body: please confirm the inspection window with the machine shop.",
    captured: false,
    task_id: null,
    ...overrides,
  };
}

export function makeMailboxStatus(overrides: Partial<MailboxStatus> = {}): MailboxStatus {
  return {
    available: true,
    provider: "imap",
    mailbox: "INBOX",
    message_count: 0,
    captured_count: 0,
    detail: null,
    ...overrides,
  };
}
