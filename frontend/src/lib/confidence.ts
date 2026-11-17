/**
 * The redraw confidence of a page (#132), as the Redrawn view shows it: the server scores
 * the redraw against the page's own ink (backend app/domain/redraw_confidence.py); this
 * module only turns the numbers into rows and the missed and added patches into shapes.
 */

import type { ConfidenceMark, RedrawConfidence } from "../api/types";

/** The parts in the order the view draws them, with their names for people. */
export const PART_LABELS: { key: string; label: string }[] = [
  { key: "walls", label: "Walls" },
  { key: "openings", label: "Doors and windows" },
  { key: "fixtures", label: "Fixtures" },
  { key: "rooms", label: "Room names" },
  { key: "dimensions", label: "Dimensions" },
  { key: "heights", label: "Heights" },
  { key: "text", label: "Other text" },
];

export interface ConfidenceRow {
  key: string;
  label: string;
  count: number;
  /** Share of the part on ink, or null when nothing of it is drawn. */
  onInk: string | null;
  /** Share of the page's ink this part accounts for. */
  covers: string;
}

export function percent(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export function confidenceRows(c: RedrawConfidence): ConfidenceRow[] {
  const rows: ConfidenceRow[] = [];
  for (const { key, label } of PART_LABELS) {
    const p = c.parts[key];
    if (!p) continue;
    rows.push({
      key,
      label,
      count: p.count,
      onInk: p.count > 0 ? percent(p.on_ink) : null,
      covers: percent(p.ink_covered),
    });
  }
  return rows;
}

/** SVG `points` of a patch outline, or null if it is not at least a triangle. */
export function markPoints(mark: ConfidenceMark): string | null {
  if (mark.polygon.length < 3) return null;
  return mark.polygon.map(([x, y]) => `${x},${y}`).join(" ");
}
