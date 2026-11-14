import { describe, expect, it } from "vitest";
import type { RedrawElement } from "./redraw";
import {
  buildSketchSheet,
  isSketchDocument,
  planElements,
  polylinePoints,
  redrawScaleBar,
  SKETCH_SOURCE,
} from "./sketchSheet";

function el(over: Partial<RedrawElement> & Pick<RedrawElement, "id" | "kind">): RedrawElement {
  return {
    bbox: [0, 0, 10, 10],
    label: null,
    name: null,
    text: null,
    properties: {},
    source: SKETCH_SOURCE,
    confidence: 0.8,
    ...over,
  };
}

// The shapes as the backend stores them (app/domain/sketch_drawing.py), page pixels.
const band = [
  [94, 106],
  [200, 106],
  [200, 94],
  [94, 94],
];
const wall = el({
  id: "w1",
  kind: "wall",
  properties: { pieces_px: [band], thickness: "outer", polygon_px: band },
});
const door = el({
  id: "d1",
  kind: "door",
  properties: {
    leaf_px: [
      [200, 100],
      [200, 160],
    ],
    arc_px: [
      [200, 160],
      [242.4, 142.4],
      [260, 100],
    ],
  },
});
const windowEl = el({
  id: "n1",
  kind: "window",
  properties: {
    lines_px: [
      [
        [300, 103],
        [380, 103],
      ],
      [
        [300, 97],
        [380, 97],
      ],
    ],
  },
});
const room = el({
  id: "r1",
  kind: "room",
  name: "bedroom",
  label: "bedroom",
  text: "bedroom",
  properties: { label_px: [300, 400], font_px: 24 },
});

describe("polylinePoints", () => {
  it("turns points into an SVG points list and refuses fewer than two", () => {
    expect(
      polylinePoints([
        [0, 0],
        [1, 2],
      ]),
    ).toBe("0,0 1,2");
    expect(polylinePoints([[0, 0]])).toBeNull();
    expect(
      polylinePoints([
        [0, "1"],
        [2, 2],
      ]),
    ).toBeNull();
    expect(polylinePoints("0,0 1,1")).toBeNull();
  });
});

describe("buildSketchSheet", () => {
  it("draws the stored shapes of each kind", () => {
    const sheet = buildSketchSheet([wall, door, windowEl, room]);
    expect(sheet.walls).toEqual([
      { id: "w1", pieces: ["94,106 200,106 200,94 94,94"], outer: true },
    ]);
    expect(sheet.doors).toEqual([
      { id: "d1", leaf: "200,100 200,160", arc: "200,160 242.4,142.4 260,100" },
    ]);
    expect(sheet.windows).toEqual([{ id: "n1", lines: ["300,103 380,103", "300,97 380,97"] }]);
    expect(sheet.rooms).toEqual([{ id: "r1", name: "bedroom", x: 300, y: 400, size: 24 }]);
    expect(sheet.texts).toEqual([]);
  });

  it("leaves out everything ingest found: only the model's plan is drawn", () => {
    const ocr = el({ id: "t1", kind: "text", text: "bedr00m", source: "ocr" });
    const vision = { ...door, id: "d2", source: "vision" };
    const upscaled = { ...wall, id: "w2", source: "upscale" };
    const sheet = buildSketchSheet([ocr, vision, upscaled, wall]);
    expect(sheet.walls.map((w) => w.id)).toEqual(["w1"]);
    expect(sheet.doors).toEqual([]);
    expect(sheet.texts).toEqual([]);
  });

  it("draws written text, and no area or dimension of its own", () => {
    const note = el({
      id: "x1",
      kind: "text",
      text: "N",
      properties: { label_px: [900, 50], font_px: 16, written: true },
    });
    // Even if a room somehow carried an area, the sketch sheet has nowhere to show it.
    const withArea = { ...room, properties: { ...room.properties, area_m2: 12 } };
    const sheet = buildSketchSheet([note, withArea]);
    expect(sheet.texts).toEqual([{ id: "x1", text: "N", x: 900, y: 50, size: 16 }]);
    expect(JSON.stringify(sheet)).not.toContain("m²");
    expect(sheet.rooms[0]).not.toHaveProperty("area");
  });

  it("skips shapes whose stored geometry is malformed", () => {
    const sheet = buildSketchSheet([
      el({ id: "w", kind: "wall", properties: { pieces_px: "no" } }),
      el({ id: "d", kind: "door", properties: { leaf_px: [[1, 1]], arc_px: [] } }),
      el({ id: "r", kind: "room", text: "hall", properties: { label_px: [1], font_px: 9 } }),
      el({ id: "t", kind: "text", text: "  ", properties: { label_px: [1, 1], font_px: 9 } }),
    ]);
    expect(sheet).toEqual({ walls: [], doors: [], windows: [], rooms: [], texts: [] });
  });
});

describe("redrawScaleBar", () => {
  const page = { width: 1000, height: 800 };

  it("never draws a scale bar on a sketch, even when ingest derived a scale", () => {
    // Raster ingest can set mm_per_px from the file's DPI and an OCR'd "1:50" note, or
    // from misread dimensions. A sketch has no scale: no bar.
    expect(redrawScaleBar(page, 0.26, true)).toBeNull();
  });

  it("keeps the scale bar on other formats when the scale is known", () => {
    // 0.5 mm per px: 2 m is 4000 px (> 200 px, a fifth of the width), 0.1 m is 200 px.
    expect(redrawScaleBar(page, 0.5, false)?.label).toBe("10 cm");
    expect(redrawScaleBar(page, null, false)).toBeNull();
  });
});

describe("isSketchDocument", () => {
  it("is true for raster image uploads, which get the sketch redraw", () => {
    expect(isSketchDocument("image")).toBe(true);
    for (const kind of ["pdf", "svg", "dxf", "dwg", "ifc"] as const) {
      expect(isSketchDocument(kind)).toBe(false);
    }
  });
});

describe("planElements", () => {
  const ocr = el({ id: "t1", kind: "text", source: "ocr" });

  it("on a redrawn sketch, offers only the model's elements to point at", () => {
    expect(planElements([ocr, wall], true).map((e) => e.id)).toEqual(["w1"]);
  });

  it("otherwise offers every element, the same array", () => {
    const all = [ocr, wall];
    expect(planElements(all, false)).toBe(all);
  });
});
