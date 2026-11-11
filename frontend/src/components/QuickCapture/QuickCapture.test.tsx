import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { QuickCapture } from "./QuickCapture";

describe("QuickCapture", () => {
  it("submits a trimmed title and clears the input", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<QuickCapture onSubmit={onSubmit} onOpenFull={() => {}} />);

    const input = screen.getByPlaceholderText("Capture a responsibility…");
    await user.type(input, "  Call the machine shop  ");
    await user.click(screen.getByRole("button", { name: "Capture" }));

    expect(onSubmit).toHaveBeenCalledWith("Call the machine shop");
    expect(input).toHaveValue("");
  });

  it("does not submit an empty title", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<QuickCapture onSubmit={onSubmit} onOpenFull={() => {}} />);
    await user.click(screen.getByRole("button", { name: "Capture" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("opens the full dialog from + New", async () => {
    const user = userEvent.setup();
    const onOpenFull = vi.fn();
    render(<QuickCapture onSubmit={vi.fn()} onOpenFull={onOpenFull} />);
    await user.click(screen.getByRole("button", { name: "+ New" }));
    expect(onOpenFull).toHaveBeenCalled();
  });
});
