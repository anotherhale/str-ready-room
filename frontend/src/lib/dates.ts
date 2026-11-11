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
