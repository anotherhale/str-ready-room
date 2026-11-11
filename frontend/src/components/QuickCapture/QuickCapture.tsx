import { useState } from "react";

export interface QuickCaptureProps {
  onSubmit: (title: string) => Promise<void> | void;
  onOpenFull: () => void;
  busy?: boolean;
}

// Minimal-friction capture: type a title, press Enter.  The full dialog is one
// click away for anything more.
export function QuickCapture({ onSubmit, onOpenFull, busy }: QuickCaptureProps) {
  const [title, setTitle] = useState("");

  async function submit() {
    const trimmed = title.trim();
    if (!trimmed) return;
    await onSubmit(trimmed);
    setTitle("");
  }

  return (
    <form
      className="quick-capture"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
      aria-label="Quick capture"
    >
      <label htmlFor="quick-capture-input" className="hint">
        Quick capture
      </label>
      <input
        id="quick-capture-input"
        type="text"
        placeholder="Capture a responsibility…"
        value={title}
        maxLength={300}
        onChange={(e) => setTitle(e.target.value)}
      />
      <button className="btn primary" type="submit" disabled={busy || !title.trim()}>
        Capture
      </button>
      <button className="btn" type="button" onClick={onOpenFull}>
        + New
      </button>
    </form>
  );
}
