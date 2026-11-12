// Typed mirrors of the backend transport contract.  These are *contract*
// types only — all urgency and recurrence values are derived by the backend
// and consumed here verbatim.  No business rules live in this file.

export type Urgency = "overdue" | "due" | "watch" | "up_next" | "normal" | "completed";

export type TaskStatus = "open" | "completed";

export type Priority = "low" | "normal" | "high" | "critical";

export type Frequency = "daily" | "weekly" | "monthly" | "quarterly" | "yearly";

export type EndType = "never" | "count" | "on_date";

export interface RecurrenceSummary {
  rule_id: string;
  name: string;
  frequency: Frequency;
  interval: number;
  day_of_week: number | null;
  end_type: EndType;
  active: boolean;
  occurrences_generated: number;
  next_occurrence: string | null;
}

export interface Task {
  id: string;
  owner_id: string;
  title: string;
  description: string | null;
  category: string;
  status: TaskStatus;
  priority: Priority;
  due_date: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  series_id: string | null;
  occurrence_number: number;
  recurrence: RecurrenceSummary | null;
  urgency: Urgency;
  days_until_due: number | null;
}

export interface TaskListResponse {
  items: Task[];
  total: number;
}

export interface Counts {
  overdue: number;
  due: number;
  watch: number;
  horizon: number;
  completed_this_week: number;
}

export interface Dashboard {
  today: string;
  timezone: string;
  greeting_name: string;
  warning_window_days: number;
  watch_label: string;
  readiness_summary: string;
  counts: Counts;
  today_tasks: Task[];
  watch_tasks: Task[];
  horizon_tasks: Task[];
}

export interface Briefing {
  date: string;
  timezone: string;
  today: Task[];
  upcoming: Task[];
  overdue: Task[];
  recurring_obligations: Task[];
  look_ahead: string;
}

export interface Category {
  id: string;
  name: string;
  active: boolean;
  is_default: boolean;
}

export interface Settings {
  warning_window_days: number;
  timezone: string;
  categories: Category[];
}

export interface TimezonesResponse {
  timezones: string[];
  default_timezone: string;
}

export interface RecurrenceOverviewItem {
  rule_id: string;
  name: string;
  frequency: Frequency;
  interval: number;
  day_of_week: number | null;
  end_type: EndType;
  active: boolean;
  occurrences_generated: number;
  next_occurrence: string | null;
}

export interface UpcomingOccurrence {
  name: string;
  date: string;
}

export interface RecurrenceOverview {
  rules: RecurrenceOverviewItem[];
  upcoming: UpcomingOccurrence[];
}

export interface RecurrenceInput {
  name: string;
  frequency: Frequency;
  interval?: number;
  day_of_week?: number | null;
  anchor_date?: string | null;
  end_type?: EndType;
  end_count?: number | null;
  end_date?: string | null;
  active?: boolean;
}

export interface TaskCreateInput {
  title: string;
  category: string;
  priority?: Priority;
  description?: string | null;
  due_date?: string | null;
  recurrence?: RecurrenceInput | null;
}

export interface TaskUpdateInput {
  title?: string;
  category?: string;
  priority?: Priority;
  description?: string | null;
  description_set?: boolean;
  due_date?: string | null;
  due_date_set?: boolean;
  recurrence?: RecurrenceInput | null;
  recurrence_set?: boolean;
}

export interface Principal {
  id: string;
  display_name: string;
  timezone: string;
  roles: string[];
}

export interface ResetSummary {
  tasks_deleted: number;
  rules_deleted: number;
  categories_restored: number;
}

export interface Health {
  status: string;
  environment: string;
  database_adapter: string;
  auth_provider: string;
}

// -- calendar -------------------------------------------------------------
export interface CalendarEvent {
  id: string;
  uid: string;
  calendar_id: string;
  summary: string;
  start: string;
  end: string | null;
  all_day: boolean;
  location: string | null;
  description: string | null;
  task_id: string | null;
  captured: boolean;
}

export interface CalendarAgenda {
  date: string;
  timezone: string;
  window_days: number;
  available: boolean;
  events: CalendarEvent[];
  detail: string | null;
}

export interface CalendarStatus {
  available: boolean;
  provider: string | null;
  calendar_id: string | null;
  cached_events: number;
  last_synced_at: string | null;
  detail: string | null;
}

export interface CalendarSyncResult {
  fetched: number;
  created: number;
  updated: number;
  pruned: number;
  synced_at: string;
}

export interface CalendarEventInput {
  summary: string;
  start: string;
  end?: string | null;
  all_day?: boolean;
  location?: string | null;
  description?: string | null;
  calendar_id?: string | null;
}

export interface CalendarCaptureInput {
  category?: string;
  priority?: Priority;
  due_date?: string | null;
  title?: string;
  description?: string | null;
}

// -- email ----------------------------------------------------------------
export interface EmailSummary {
  message_id: string;
  sender: string;
  subject: string;
  received_at: string | null;
  snippet: string;
  captured: boolean;
  task_id: string | null;
}

export interface EmailMessage {
  message_id: string;
  sender: string;
  subject: string;
  received_at: string | null;
  body: string;
  captured: boolean;
  task_id: string | null;
}

export interface MailboxStatus {
  available: boolean;
  provider: string | null;
  mailbox: string | null;
  message_count: number;
  captured_count: number;
  detail: string | null;
}

export interface EmailCaptureInput {
  category?: string;
  priority?: Priority;
  due_date?: string | null;
  title?: string;
}
