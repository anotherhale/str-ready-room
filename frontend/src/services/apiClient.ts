// Typed API client.  One thin boundary over fetch that speaks the backend
// contract.  Business rules are not duplicated here; this only moves data.

import type {
  Briefing,
  CalendarAgenda,
  CalendarCaptureInput,
  CalendarEvent,
  CalendarEventInput,
  CalendarStatus,
  CalendarSyncResult,
  Category,
  Dashboard,
  EmailCaptureInput,
  EmailMessage,
  EmailSummary,
  Health,
  MailboxStatus,
  Principal,
  RecurrenceInput,
  RecurrenceOverview,
  ResetSummary,
  Settings,
  Task,
  TaskCreateInput,
  TaskListResponse,
  TaskUpdateInput,
  TimezonesResponse,
} from "../types";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      ...init,
    });
  } catch (err) {
    throw new ApiError(0, "network_error", "Unable to reach the server.", err);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const body = text ? safeJson(text) : null;

  if (!response.ok) {
    const { code, message } = extractError(body, response.status);
    throw new ApiError(response.status, code, message, body);
  }
  return body as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

// Maps both the typed error payload ({code, message}) and FastAPI's native
// 422 validation shape ({detail: [...]}) to a readable message.
function extractError(body: unknown, status: number): { code: string; message: string } {
  if (body && typeof body === "object") {
    const obj = body as Record<string, unknown>;
    if (typeof obj.message === "string") {
      return { code: typeof obj.code === "string" ? obj.code : "error", message: obj.message };
    }
    if (Array.isArray(obj.detail)) {
      const messages = obj.detail
        .map((d) => {
          if (d && typeof d === "object" && "msg" in d) {
            const loc = Array.isArray((d as { loc?: unknown[] }).loc)
              ? (d as { loc: unknown[] }).loc.filter((p) => p !== "body").join(".")
              : "";
            const msg = String((d as { msg: unknown }).msg);
            return loc ? `${loc}: ${msg}` : msg;
          }
          return String(d);
        })
        .join("; ");
      return { code: "validation_error", message: messages || "Validation failed." };
    }
    if (typeof obj.detail === "string") {
      return { code: "error", message: obj.detail };
    }
  }
  return { code: "error", message: `Request failed (${status}).` };
}

function query(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, value);
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  health: () => request<Health>("/health"),
  me: () => request<Principal>("/me"),

  getDashboard: () => request<Dashboard>("/dashboard"),
  getBriefing: () => request<Briefing>("/briefing"),

  listTasks: (filters: { status?: string; category?: string; search?: string } = {}) =>
    request<TaskListResponse>(`/tasks${query(filters)}`),
  getTask: (id: string) => request<Task>(`/tasks/${id}`),
  createTask: (input: TaskCreateInput) =>
    request<Task>("/tasks", { method: "POST", body: JSON.stringify(input) }),
  updateTask: (id: string, input: TaskUpdateInput) =>
    request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
  completeTask: (id: string) => request<Task>(`/tasks/${id}/complete`, { method: "POST" }),
  reopenTask: (id: string) => request<Task>(`/tasks/${id}/reopen`, { method: "POST" }),
  deleteTask: (id: string) => request<void>(`/tasks/${id}`, { method: "DELETE" }),

  getRecurrenceOverview: () => request<RecurrenceOverview>("/recurrence"),
  previewRecurrence: (input: RecurrenceInput & { count?: number }) =>
    request<{ dates: string[] }>("/recurrence/preview", {
      method: "POST",
      body: JSON.stringify(input),
    }),

  getSettings: () => request<Settings>("/settings"),
  updateSettings: (input: { warning_window_days?: number; timezone?: string }) =>
    request<Settings>("/settings", { method: "PATCH", body: JSON.stringify(input) }),
  listTimezones: () => request<TimezonesResponse>("/timezones"),

  listCategories: () => request<Category[]>("/categories"),
  createCategory: (name: string) =>
    request<Category>("/categories", { method: "POST", body: JSON.stringify({ name }) }),
  updateCategory: (id: string, input: { name?: string; active?: boolean }) =>
    request<Category>(`/categories/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
  deleteCategory: (id: string) => request<void>(`/categories/${id}`, { method: "DELETE" }),

  resetDemo: () => request<ResetSummary>("/demo/reset", { method: "POST" }),

  // -- calendar (optional integration) -----------------------------------
  getCalendarAgenda: (days?: number) =>
    request<CalendarAgenda>(`/calendar/agenda${query({ days: days ? String(days) : undefined })}`),
  getCalendarStatus: () => request<CalendarStatus>("/calendar/status"),
  syncCalendar: () => request<CalendarSyncResult>("/calendar/sync", { method: "POST" }),
  createCalendarEvent: (input: CalendarEventInput) =>
    request<CalendarEvent>("/calendar/events", { method: "POST", body: JSON.stringify(input) }),
  deleteCalendarEvent: (id: string) =>
    request<void>(`/calendar/events/${encodeURIComponent(id)}`, { method: "DELETE" }),
  captureCalendarEvent: (id: string, input: CalendarCaptureInput) =>
    request<Task>(`/calendar/events/${encodeURIComponent(id)}/tasks`, {
      method: "POST",
      body: JSON.stringify(input),
    }),

  // -- email (optional integration) --------------------------------------
  listMessages: (limit?: number) =>
    request<EmailSummary[]>(`/mail/messages${query({ limit: limit ? String(limit) : undefined })}`),
  getMailboxStatus: () => request<MailboxStatus>("/mail/status"),
  getMessage: (messageId: string) =>
    request<EmailMessage>(`/mail/messages/${encodeURIComponent(messageId)}`),
  captureMessage: (messageId: string, input: EmailCaptureInput) =>
    request<Task>(`/mail/messages/${encodeURIComponent(messageId)}/tasks`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
};
