import { describe, expect, it } from "vitest";
import type { RedrawConfidence } from "../api/types";
import { confidenceRows, markPoints, percent } from "./confidence";

const part = (count: number, on_ink: number, ink_covered: number) => ({
  count,
  drawn_px: count * 100,
  on_ink,
  ink_covered,
});

const SCORED: RedrawConfidence = {
  score: 0.862,
  covered: 0.76,
  on_ink: 0.997,
  ink_px: 29500,
  parts: {
    walls: part(158, 0.998, 0.669),
    openings: part(0, 1, 0),
    rooms: part(3, 0.9, 0.005),
    dimensions: part(8, 1, 0.024),
    heights: part(13, 1, 0.044),
    text: part(8, 0.958, 0.018),
  },
  missed: [
    {
      polygon: [
        [298, 298],
        [311, 298],
        [311, 311],
        [298, 311],
      ],
      px: 100,
    },
  ],
  added: [],
};

describe("percent", () => {
  it("rounds a share to whole percent", () => {
    expect(percent(0.862)).toBe("86%");
    expect(percent(0.9975)).toBe("100%");
    expect(percent(0)).toBe("0%");
  });
});

describe("confidenceRows", () => {
  it("lists every part in the view's order with its numbers", () => {
    const rows = confidenceRows(SCORED);
    expect(rows.map((r) => r.label)).toEqual([
      "Walls",
      "Doors and windows",
      "Room names",
      "Dimensions",
      "Heights",
      "Other text",
    ]);
    expect(rows[0]).toEqual({
      key: "walls",
      label: "Walls",
      count: 158,
      onInk: "100%",
      covers: "67%",
    });
    // Nothing drawn: there is no share on ink to show.
    expect(rows[1]).toEqual({
      key: "openings",
      label: "Doors and windows",
      count: 0,
      onInk: null,
      covers: "0%",
    });
  });

  it("leaves out a part the server did not send", () => {
    const rows = confidenceRows({ ...SCORED, parts: { walls: part(1, 1, 1) } });
    expect(rows.map((r) => r.key)).toEqual(["walls"]);
  });
});

describe("markPoints", () => {
  it("turns a patch outline into SVG points", () => {
    expect(markPoints(SCORED.missed[0])).toBe("298,298 311,298 311,311 298,311");
  });

  it("rejects an outline of fewer than three points", () => {
    expect(
      markPoints({
        polygon: [
          [0, 0],
          [1, 1],
        ],
        px: 2,
      }),
    ).toBeNull();
  });
});
