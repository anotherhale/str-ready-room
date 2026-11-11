import { describe, expect, it } from "vitest";

import { describeRecurrence } from "../lib/recurrence";
import { urgencyGlyph, urgencyLabel, urgencyPresentation } from "../lib/urgency";
import type { Urgency } from "../types";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

describe("urgency presentation", () => {
  it("maps every urgency to a readable label and glyph", () => {
    const states: Urgency[] = ["overdue", "due", "watch", "up_next", "normal", "completed"];
    for (const state of states) {
      expect(urgencyLabel(state)).toBeTruthy();
      expect(urgencyGlyph(state)).toBeTruthy();
    }
  });

  it("uses the expected tones", () => {
    expect(urgencyPresentation("overdue").tone).toBe("critical");
    expect(urgencyPresentation("due").tone).toBe("warning");
    expect(urgencyPresentation("completed").tone).toBe("ok");
    expect(urgencyPresentation("up_next").tone).toBe("neutral");
  });
});

describe("describeRecurrence", () => {
  it("describes weekly cadence with a weekday", () => {
    expect(describeRecurrence("weekly", 1, 0, WEEKDAYS)).toBe("Every week on Monday");
  });

  it("describes intervals and other frequencies", () => {
    expect(describeRecurrence("weekly", 2, null, WEEKDAYS)).toBe("Every 2 weeks");
    expect(describeRecurrence("quarterly", 1, null, WEEKDAYS)).toBe("Every quarter");
    expect(describeRecurrence("monthly", 3, null, WEEKDAYS)).toBe("Every 3 months");
  });
});
