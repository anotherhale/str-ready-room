import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { InventoryView } from "./InventoryView";
import { makeTask } from "../../test/fixtures";

function baseProps(overrides = {}) {
  return {
    tasks: [
      makeTask({ id: "a", title: "Active one" }),
      makeTask({ id: "b", title: "Done one", status: "completed", urgency: "completed" }),
    ],
    total: 2,
    categories: ["General", "Maintenance"],
    filters: { status: "all", category: "all", search: "" },
    onFiltersChange: vi.fn(),
    onEdit: vi.fn(),
    onComplete: vi.fn(),
    onReopen: vi.fn(),
    onDelete: vi.fn(),
    onNew: vi.fn(),
    busy: false,
    ...overrides,
  };
}

describe("InventoryView", () => {
  it("separates active from completed tasks", () => {
    render(<InventoryView {...baseProps()} />);
    expect(screen.getByText("Active one")).toBeInTheDocument();
    expect(screen.getByText("Done one")).toBeInTheDocument();
    // Section headings "Active"/"Completed" plus the completed task's badge.
    expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Completed").length).toBeGreaterThan(0);
  });

  it("propagates search changes", async () => {
    const user = userEvent.setup();
    const onFiltersChange = vi.fn();
    render(<InventoryView {...baseProps({ onFiltersChange })} />);
    await user.type(screen.getByPlaceholderText("Title or notes…"), "tow");
    expect(onFiltersChange).toHaveBeenCalledWith({ search: "t" });
  });

  it("shows an empty message when no active tasks match", () => {
    render(
      <InventoryView
        {...baseProps({
          tasks: [makeTask({ id: "b", title: "Done one", status: "completed", urgency: "completed" })],
        })}
      />,
    );
    expect(
      screen.getByText("No active responsibilities match these filters."),
    ).toBeInTheDocument();
  });
});
