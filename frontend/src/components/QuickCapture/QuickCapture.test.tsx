import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { QuickCapture } from "./QuickCapture";

const CATEGORIES = ["General", "Maintenance", "Logistics"];

describe("QuickCapture", () => {
  it("submits a trimmed title with the selected fields and clears the input", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <QuickCapture categories={CATEGORIES} onSubmit={onSubmit} onOpenFull={() => {}} />,
    );

    const input = screen.getByPlaceholderText("Capture a responsibility…");
    await user.type(input, "  Call the machine shop  ");
    await user.selectOptions(screen.getByLabelText("Category"), "Maintenance");
    await user.selectOptions(screen.getByLabelText("Priority"), "high");
    await user.clear(screen.getByLabelText("Due date"));
    await user.type(screen.getByLabelText("Due date"), "2026-11-20");
    await user.click(screen.getByRole("button", { name: "Capture" }));

    expect(onSubmit).toHaveBeenCalledWith({
      title: "Call the machine shop",
      category: "Maintenance",
      priority: "high",
      due_date: "2026-11-20",
    });
    expect(input).toHaveValue("");
  });

  it("defaults to the first category, normal priority, and today's date", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <QuickCapture categories={CATEGORIES} onSubmit={onSubmit} onOpenFull={() => {}} />,
    );

    expect(screen.getByLabelText("Category")).toHaveValue("General");
    expect(screen.getByLabelText("Priority")).toHaveValue("normal");

    await user.type(screen.getByPlaceholderText("Capture a responsibility…"), "Quick item");
    await user.click(screen.getByRole("button", { name: "Capture" }));

    const submitted = onSubmit.mock.calls[0][0];
    expect(submitted.category).toBe("General");
    expect(submitted.priority).toBe("normal");
    expect(submitted.due_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("sends a null due date when the date field is cleared", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <QuickCapture categories={CATEGORIES} onSubmit={onSubmit} onOpenFull={() => {}} />,
    );

    await user.type(screen.getByPlaceholderText("Capture a responsibility…"), "No date");
    await user.clear(screen.getByLabelText("Due date"));
    await user.click(screen.getByRole("button", { name: "Capture" }));

    expect(onSubmit.mock.calls[0][0].due_date).toBeNull();
  });

  it("does not submit an empty title", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <QuickCapture categories={CATEGORIES} onSubmit={onSubmit} onOpenFull={() => {}} />,
    );
    await user.click(screen.getByRole("button", { name: "Capture" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("opens the full dialog from + New", async () => {
    const user = userEvent.setup();
    const onOpenFull = vi.fn();
    render(
      <QuickCapture categories={CATEGORIES} onSubmit={vi.fn()} onOpenFull={onOpenFull} />,
    );
    await user.click(screen.getByRole("button", { name: "+ New" }));
    expect(onOpenFull).toHaveBeenCalled();
  });
});
