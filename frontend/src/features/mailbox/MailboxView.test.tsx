import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { MailboxView } from "./MailboxView";
import { makeEmailMessage, makeEmailSummary, makeMailboxStatus, makeSettings } from "../../test/fixtures";

const categories = makeSettings().categories;

function renderMailbox(overrides: Partial<Parameters<typeof MailboxView>[0]> = {}) {
  const props = {
    messages: [makeEmailSummary()],
    status: makeMailboxStatus({ message_count: 1 }),
    categories,
    timezone: "America/New_York",
    onLoadMessage: vi.fn(async () => makeEmailMessage()),
    onCapture: vi.fn(async () => {}),
    busy: false,
    ...overrides,
  };
  return render(<MailboxView {...props} />);
}

describe("MailboxView", () => {
  it("lists messages and loads a body on selection", async () => {
    renderMailbox();
    expect(screen.getByText("Tow bar inspection")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Tow bar inspection/ }));
    expect(await screen.findByText(/Full body: please confirm the inspection window/)).toBeInTheDocument();
  });

  it("captures a message through the dialog", async () => {
    const onCapture = vi.fn(async () => {});
    renderMailbox({ onCapture });

    await userEvent.click(screen.getByRole("button", { name: /Tow bar inspection/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Capture" }));

    const dialog = screen.getByRole("dialog", { name: "Capture as responsibility" });
    expect(dialog).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Capture" }));

    expect(onCapture).toHaveBeenCalledWith(
      "<m1@x>",
      expect.objectContaining({ title: "Tow bar inspection" }),
    );
  });

  it("marks a captured message and hides the Capture action", async () => {
    renderMailbox({
      messages: [makeEmailSummary({ captured: true, task_id: "t1" })],
      onLoadMessage: vi.fn(async () => makeEmailMessage({ captured: true, task_id: "t1" })),
    });
    expect(screen.getByText("Captured")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Tow bar inspection/ }));
    expect(await screen.findByText("In inventory")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Capture" })).not.toBeInTheDocument();
  });

  it("updates the open message detail immediately after a capture", async () => {
    // Regression: the detail pane used to render the snapshot taken when the
    // message was opened, so it kept showing "Capture" until the message was
    // reopened.  Capture state must come from the refreshed list.
    const summary = makeEmailSummary({ captured: false });
    const onCapture = vi.fn(async (_id: string, _input: unknown) => {});

    function Harness() {
      const [messages, setMessages] = useState([summary]);
      return (
        <MailboxView
          messages={messages}
          status={makeMailboxStatus({ message_count: 1 })}
          categories={categories}
          timezone="America/New_York"
          onLoadMessage={vi.fn(async () => makeEmailMessage({ captured: false }))}
          onCapture={async (id, input) => {
            await onCapture(id, input);
            setMessages((prev) =>
              prev.map((m) => (m.message_id === id ? { ...m, captured: true, task_id: "t1" } : m)),
            );
          }}
          busy={false}
        />
      );
    }
    render(<Harness />);

    await userEvent.click(screen.getByRole("button", { name: /Tow bar inspection/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Capture" }));

    const dialog = screen.getByRole("dialog", { name: "Capture as responsibility" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Capture" }));

    // No reopen: the detail pane flips to "In inventory" on its own.
    expect(onCapture).toHaveBeenCalled();
    expect(await screen.findByText("In inventory")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Capture" })).not.toBeInTheDocument();
  });

  it("shows an unavailable notice when the integration is off", () => {
    renderMailbox({
      messages: [],
      status: makeMailboxStatus({ available: false, detail: "Mailbox integration is not configured." }),
    });
    expect(screen.getByText(/Mailbox integration is not available/)).toBeInTheDocument();
  });

  it("shows an empty inbox state", () => {
    renderMailbox({ messages: [] });
    expect(screen.getByText("No messages.")).toBeInTheDocument();
  });
});
