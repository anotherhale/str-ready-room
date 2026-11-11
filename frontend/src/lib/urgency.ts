// Presentation-only mappings for the server-derived urgency value.
// The backend is authoritative; this file must never compute urgency itself.

import type { Urgency } from "../types";

export interface UrgencyPresentation {
  label: string;
  glyph: string;
  tone: "critical" | "warning" | "neutral" | "ok";
}

const PRESENTATION: Record<Urgency, UrgencyPresentation> = {
  overdue: { label: "Overdue", glyph: "▲", tone: "critical" },
  due: { label: "Due today", glyph: "◆", tone: "warning" },
  watch: { label: "Watch", glyph: "◐", tone: "warning" },
  up_next: { label: "On the Horizon", glyph: "◇", tone: "neutral" },
  normal: { label: "Normal", glyph: "○", tone: "neutral" },
  completed: { label: "Completed", glyph: "✔", tone: "ok" },
};

export function urgencyPresentation(urgency: Urgency): UrgencyPresentation {
  return PRESENTATION[urgency] ?? PRESENTATION.normal;
}

export function urgencyLabel(urgency: Urgency): string {
  return urgencyPresentation(urgency).label;
}

export function urgencyGlyph(urgency: Urgency): string {
  return urgencyPresentation(urgency).glyph;
}
