import { describe, expect, it } from "vitest";

import { describeDue, formatLongDate, formatShortDate, localGreeting } from "../lib/dates";

describe("describeDue", () => {
  it("describes future, today, and overdue gaps", () => {
    expect(describeDue(0)).toBe("Due today");
    expect(describeDue(1)).toBe("Due tomorrow");
    expect(describeDue(3)).toBe("Due in 3 days");
    expect(describeDue(-1)).toBe("1 day overdue");
    expect(describeDue(-2)).toBe("2 days overdue");
    expect(describeDue(null)).toBe("No due date");
  });
});

describe("date formatting", () => {
  it("formats plain dates without timezone drift", () => {
    expect(formatLongDate("2026-03-10")).toBe("Tuesday, March 10, 2026");
    expect(formatShortDate("2026-03-10")).toBe("Tue Mar 10");
  });
});

describe("localGreeting", () => {
  it("varies by hour of day", () => {
    expect(localGreeting(new Date(2026, 2, 10, 8))).toBe("Good morning");
    expect(localGreeting(new Date(2026, 2, 10, 14))).toBe("Good afternoon");
    expect(localGreeting(new Date(2026, 2, 10, 20))).toBe("Good evening");
  });
});
