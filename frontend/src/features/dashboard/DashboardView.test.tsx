import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardView } from "./DashboardView";
import { makeDashboard, makeTask } from "../../test/fixtures";

const noop = vi.fn();

function renderDashboard(overrides = {}) {
  return render(
    <DashboardView
      dashboard={makeDashboard(overrides)}
      onEdit={noop}
      onComplete={noop}
      onReopen={noop}
      onOpenBriefing={noop}
      onOpenInventory={noop}
      busy={false}
    />,
  );
}

describe("DashboardView", () => {
  it("renders the greeting, counts, and watch label", () => {
    renderDashboard();
    expect(screen.getByText(/Maverick/)).toBeInTheDocument();
    expect(screen.getByText("Overdue")).toBeInTheDocument();
    expect(screen.getByText("Watch")).toBeInTheDocument();
    expect(screen.getByText("Done this week")).toBeInTheDocument();
    expect(screen.getByText("3-Day Watch")).toBeInTheDocument();
  });

  it("keeps overdue tasks visible in the Today section", () => {
    renderDashboard({
      today_tasks: [
        makeTask({ id: "o1", title: "Submit training records", urgency: "overdue", days_until_due: -2 }),
      ],
    });
    expect(screen.getByText("Submit training records")).toBeInTheDocument();
    expect(screen.getByText("2 days overdue")).toBeInTheDocument();
  });

  it("shows empty-state guidance when a section has nothing", () => {
    renderDashboard();
    expect(screen.getByText("Nothing due today. You are ahead of the jet.")).toBeInTheDocument();
    expect(screen.getByText("No responsibilities inside the warning window.")).toBeInTheDocument();
  });
});
