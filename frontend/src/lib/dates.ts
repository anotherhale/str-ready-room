// Date formatting helpers.  These format values the backend already resolved
// (plain `date` strings, naive-UTC timestamps); they do not decide "today".

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

// Parse a plain YYYY-MM-DD as a *local* date (no timezone shifting).
export function parsePlainDate(value: string): Date {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1);
}

export function formatLongDate(value: string): string {
  const date = parsePlainDate(value);
  return `${WEEKDAYS[(date.getDay() + 6) % 7]}, ${MONTHS[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
}

export function formatShortDate(value: string): string {
  const date = parsePlainDate(value);
  return `${WEEKDAY_SHORT[(date.getDay() + 6) % 7]} ${MONTHS[date.getMonth()].slice(0, 3)} ${date.getDate()}`;
}

// Describe the gap between the operator's local today and a due date.  The
// day count itself comes from the server (`days_until_due`); this only words it.
export function describeDue(daysUntilDue: number | null): string {
  if (daysUntilDue === null) return "No due date";
  if (daysUntilDue < -1) return `${Math.abs(daysUntilDue)} days overdue`;
  if (daysUntilDue === -1) return "1 day overdue";
  if (daysUntilDue === 0) return "Due today";
  if (daysUntilDue === 1) return "Due tomorrow";
  return `Due in ${daysUntilDue} days`;
}

export function localGreeting(now: Date = new Date()): string {
  const hour = now.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export const WEEKDAY_NAMES = WEEKDAYS;

// Format a timezone-aware ISO timestamp (as sent by the calendar provider) in
// the operator's effective timezone.  The backend owns the zone; this only
// renders the instant in it.  Returns "" for an unparseable value.
export function formatEventTime(value: string, timeZone: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  try {
    return new Intl.DateTimeFormat("en-US", {
      hour: "numeric",
      minute: "2-digit",
      timeZone,
    }).format(date);
  } catch {
    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
}

// Format a plain date string (YYYY-MM-DD) as a short weekday label.
export function formatEventDay(value: string): string {
  return formatShortDate(value.slice(0, 10));
}

// The calendar date (YYYY-MM-DD) of a timezone-aware instant, resolved in the
// operator's timezone.  Used only to group events for display.
export function localDateOf(value: string, timeZone: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      timeZone,
    }).formatToParts(date);
    const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
    return `${get("year")}-${get("month")}-${get("day")}`;
  } catch {
    return value.slice(0, 10);
  }
}
