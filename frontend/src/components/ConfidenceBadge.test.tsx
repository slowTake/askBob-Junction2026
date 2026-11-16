import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { RedrawConfidence } from "../api/types";
import { ConfidenceBadge } from "./ConfidenceBadge";

const part = (count: number, on_ink: number, ink_covered: number) => ({
  count,
  drawn_px: count,
  on_ink,
  ink_covered,
});

const SCORED: RedrawConfidence = {
  score: 0.862,
  covered: 0.76,
  on_ink: 0.997,
  ink_px: 29500,
  parts: { walls: part(158, 0.998, 0.669), openings: part(0, 1, 0) },
  missed: [
    {
      polygon: [
        [0, 0],
        [9, 0],
        [9, 9],
      ],
      px: 40,
    },
  ],
  added: [],
};

describe("ConfidenceBadge", () => {
  it("shows the score as a button and no breakdown while closed", () => {
    const html = renderToStaticMarkup(
      <ConfidenceBadge confidence={SCORED} open={false} onToggle={() => {}} />,
    );
    expect(html).toContain("Redraw confidence 86%");
    expect(html).toContain('aria-expanded="false"');
    expect(html).not.toContain('role="dialog"');
  });

  it("opens to the parts, what is missed and added, and what the score cannot tell", () => {
    const html = renderToStaticMarkup(
      <ConfidenceBadge confidence={SCORED} open onToggle={() => {}} />,
    );
    expect(html).toContain('role="dialog"');
    expect(html).toContain("Walls");
    expect(html).toContain("158");
    expect(html).toContain("Doors and windows");
    expect(html).toContain("Missed ink 24%"); // 1 - 0.76
    expect(html).toContain("Added on blank paper 0%"); // 1 - 0.997, rounded
    expect(html).toContain("cannot tell");
  });
});
