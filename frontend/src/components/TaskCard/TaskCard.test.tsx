import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TaskCard } from "./TaskCard";
import { makeTask } from "../../test/fixtures";

describe("TaskCard", () => {
  it("shows the urgency label, category, and due wording", () => {
    render(<TaskCard task={makeTask()} />);
    expect(screen.getByText("Prepare Monday morning detachment brief")).toBeInTheDocument();
    // "Due today" appears both as the urgency badge and the due wording.
    expect(screen.getAllByText("Due today").length).toBeGreaterThan(0);
    expect(screen.getByText("Detachment Operations")).toBeInTheDocument();
  });

  it("offers Complete for open tasks and Reopen for completed tasks", () => {
    const onComplete = vi.fn();
    const onReopen = vi.fn();
    const { rerender } = render(<TaskCard task={makeTask()} onComplete={onComplete} />);
    expect(screen.getByRole("button", { name: "Complete" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reopen" })).not.toBeInTheDocument();

    rerender(
      <TaskCard
        task={makeTask({ status: "completed", urgency: "completed", completed_at: "2026-03-10T00:00:00" })}
        onReopen={onReopen}
      />,
    );
    expect(screen.getByRole("button", { name: "Reopen" })).toBeInTheDocument();
  });

  it("shows a recurrence marker for recurring tasks", () => {
    render(
      <TaskCard
        task={makeTask({
          series_id: "s1",
          occurrence_number: 2,
          recurrence: {
            rule_id: "r1",
            name: "Monday brief",
            frequency: "weekly",
            interval: 1,
            day_of_week: 0,
            end_type: "never",
            active: true,
            occurrences_generated: 2,
            next_occurrence: "2026-03-17",
          },
        })}
      />,
    );
    expect(screen.getByText("Occurrence 2")).toBeInTheDocument();
    expect(screen.getByText(/Every week on Monday/)).toBeInTheDocument();
  });
});
