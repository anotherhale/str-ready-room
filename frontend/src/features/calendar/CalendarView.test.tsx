import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CalendarView } from "./CalendarView";
import { makeCalendarAgenda, makeCalendarEvent, makeCalendarStatus, makeSettings } from "../../test/fixtures";

const categories = makeSettings().categories;
const noop = vi.fn(async () => {});

function renderCalendar(overrides: Partial<Parameters<typeof CalendarView>[0]> = {}) {
  const props = {
    agenda: makeCalendarAgenda({ events: [makeCalendarEvent()] }),
    status: makeCalendarStatus(),
    categories,
    onSync: noop,
    onCapture: noop,
    onCreate: noop,
    busy: false,
    ...overrides,
  };
  return render(<CalendarView {...props} />);
}

describe("CalendarView", () => {
  it("groups events by day and shows the time in the operator's zone", () => {
    renderCalendar();
    // 07:30 America/New_York on 2026-03-10.
    expect(screen.getByText("Detachment flight quarters")).toBeInTheDocument();
    expect(screen.getByText("7:30 AM")).toBeInTheDocument();
    expect(screen.getByText("Ready room")).toBeInTheDocument();
  });

  it("offers Capture for an uncaptured event and shows a badge once captured", () => {
    const { rerender } = renderCalendar();
    expect(screen.getByRole("button", { name: "Capture" })).toBeInTheDocument();

    rerender(
      <CalendarView
        agenda={makeCalendarAgenda({ events: [makeCalendarEvent({ captured: true, task_id: "t9" })] })}
        status={makeCalendarStatus()}
        categories={categories}
        onSync={noop}
        onCapture={noop}
        onCreate={noop}
        busy={false}
      />,
    );
    expect(screen.queryByRole("button", { name: "Capture" })).not.toBeInTheDocument();
    expect(screen.getByText("In inventory")).toBeInTheDocument();
  });

  it("captures an event through the dialog", async () => {
    const onCapture = vi.fn(async () => {});
    renderCalendar({ onCapture });

    await userEvent.click(screen.getByRole("button", { name: "Capture" }));
    expect(screen.getByRole("dialog", { name: "Capture as responsibility" })).toBeInTheDocument();

    const title = screen.getByLabelText("Title *");
    expect(title).toHaveValue("Detachment flight quarters");

    const dialog = screen.getByRole("dialog", { name: "Capture as responsibility" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Capture" }));
    expect(onCapture).toHaveBeenCalledWith(
      expect.objectContaining({ id: "ev1" }),
      expect.objectContaining({ title: "Detachment flight quarters", due_date: "2026-03-10" }),
    );
  });

  it("shows an unavailable notice when the integration is off", () => {
    renderCalendar({
      agenda: makeCalendarAgenda({ available: false, detail: "Calendar integration is not configured." }),
    });
    expect(screen.getByText(/Calendar integration is not available/)).toBeInTheDocument();
  });

  it("syncs when the Sync button is pressed", async () => {
    const onSync = vi.fn(async () => {});
    renderCalendar({ onSync });
    await userEvent.click(screen.getByRole("button", { name: "Sync" }));
    expect(onSync).toHaveBeenCalled();
    expect(await screen.findByText("Calendar synced.")).toBeInTheDocument();
  });

  it("shows an empty state when there are no events", () => {
    renderCalendar({ agenda: makeCalendarAgenda({ events: [] }) });
    expect(screen.getByText("No events in the agenda window.")).toBeInTheDocument();
  });
});
