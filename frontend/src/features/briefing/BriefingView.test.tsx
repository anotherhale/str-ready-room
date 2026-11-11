import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BriefingView } from "./BriefingView";
import { makeBriefing, makeTask } from "../../test/fixtures";

describe("BriefingView", () => {
  it("renders each operational section and the look-ahead", () => {
    render(
      <BriefingView
        briefing={makeBriefing({
          overdue: [makeTask({ id: "o", title: "Overdue item", urgency: "overdue" })],
          today: [makeTask({ id: "t", title: "Today item" })],
          upcoming: [makeTask({ id: "u", title: "Upcoming item", urgency: "up_next" })],
          recurring_obligations: [makeTask({ id: "r", title: "Recurring item" })],
          look_ahead: "Two items on the horizon this week.",
        })}
      />,
    );
    expect(screen.getByText("READY ROOM — Daily Briefing")).toBeInTheDocument();
    expect(screen.getByText("Two items on the horizon this week.")).toBeInTheDocument();
    expect(screen.getByText("Overdue item")).toBeInTheDocument();
    expect(screen.getByText("Today item")).toBeInTheDocument();
    expect(screen.getByText("Upcoming item")).toBeInTheDocument();
    expect(screen.getByText("Recurring item")).toBeInTheDocument();
  });

  it("provides a print action", () => {
    const printSpy = vi.spyOn(window, "print").mockImplementation(() => {});
    render(<BriefingView briefing={makeBriefing()} />);
    screen.getByRole("button", { name: "Print briefing" }).click();
    expect(printSpy).toHaveBeenCalled();
    printSpy.mockRestore();
  });
});
