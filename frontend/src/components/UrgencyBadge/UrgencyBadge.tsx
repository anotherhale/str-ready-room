import { urgencyPresentation } from "../../lib/urgency";
import type { Urgency } from "../../types";

// Readable text label + glyph, never color alone.
export function UrgencyBadge({ urgency }: { urgency: Urgency }) {
  const { label, glyph, tone } = urgencyPresentation(urgency);
  return (
    <span className={`badge ${tone}`}>
      <span aria-hidden="true">{glyph}</span>
      <span>{label}</span>
    </span>
  );
}
