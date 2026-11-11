// Recurrence and priority presentation labels.  Human-readable wording only;
// all recurrence arithmetic is performed by the backend.

import type { EndType, Frequency, Priority } from "../types";

export const FREQUENCY_LABELS: Record<Frequency, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  quarterly: "Quarterly",
  yearly: "Yearly",
};

export const FREQUENCY_OPTIONS: Frequency[] = ["daily", "weekly", "monthly", "quarterly", "yearly"];

export const END_TYPE_LABELS: Record<EndType, string> = {
  never: "Never",
  count: "After a count",
  on_date: "On a date",
};

export const PRIORITY_LABELS: Record<Priority, string> = {
  low: "Low",
  normal: "Normal",
  high: "High",
  critical: "Critical",
};

export const PRIORITY_OPTIONS: Priority[] = ["low", "normal", "high", "critical"];

const FREQUENCY_NOUN: Record<Frequency, string> = {
  daily: "day",
  weekly: "week",
  monthly: "month",
  quarterly: "quarter",
  yearly: "year",
};

export function describeRecurrence(
  frequency: Frequency,
  interval: number,
  dayOfWeek: number | null,
  weekdayNames: string[],
): string {
  const noun = FREQUENCY_NOUN[frequency];
  const base = interval === 1 ? `Every ${noun}` : `Every ${interval} ${noun}s`;
  if (frequency === "weekly" && dayOfWeek !== null) {
    return `${base} on ${weekdayNames[dayOfWeek] ?? ""}`.trim();
  }
  return base;
}
