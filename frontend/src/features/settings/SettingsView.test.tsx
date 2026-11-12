import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SettingsView } from "./SettingsView";
import { makeSettings } from "../../test/fixtures";

// The view loads the timezone shortlist on mount; stub the client so the test
// stays deterministic.  The promise is left pending so no async state update
// fires outside React's act() (the zone list is irrelevant to these tests).
vi.mock("../../services/apiClient", () => ({
  api: {
    listTimezones: vi.fn(() => new Promise(() => {})),
  },
  ApiError: class ApiError extends Error {},
}));

function renderSettings(overrides: Partial<Parameters<typeof SettingsView>[0]> = {}) {
  const settings = makeSettings();
  const props = {
    settings,
    categories: settings.categories,
    recurrence: null,
    onSaved: vi.fn(async () => {}),
    onReset: vi.fn(async () => {}),
    ...overrides,
  };
  return render(<SettingsView {...props} />);
}

describe("SettingsView demo actions", () => {
  it("offers a Simulate arrival action and invokes it", async () => {
    const onSimulate = vi.fn(async () => {});
    renderSettings({ onSimulate });

    const button = screen.getByRole("button", { name: "Simulate arrival" });
    await userEvent.click(button);

    expect(onSimulate).toHaveBeenCalledTimes(1);
  });

  it("does not render Simulate arrival when no handler is provided", () => {
    renderSettings();
    expect(screen.queryByRole("button", { name: "Simulate arrival" })).toBeNull();
  });

  it("still offers Reset demo data alongside Simulate arrival", () => {
    renderSettings({ onSimulate: vi.fn(async () => {}) });
    expect(screen.getByRole("button", { name: "Reset demo data" })).toBeInTheDocument();
  });
});
