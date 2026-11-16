import { describe, expect, it } from "vitest";
import {
  buildCleanSheet,
  formatArea,
  polygonPoints,
  scaleBar,
  UPSCALE_SOURCE,
  type RedrawElement,
} from "./redraw";

function el(over: Partial<RedrawElement> & Pick<RedrawElement, "id" | "kind">): RedrawElement {
  return {
    bbox: null,
    label: null,
    name: null,
    text: null,
    properties: {},
    source: "ocr",
    confidence: 0.9,
    ...over,
  };
}

// One text size per page: 1/100 of its width, so 10 px here; room names 1.5× that.
const PAGE = { width: 1000, height: 800 };
const sheetOf = (elements: RedrawElement[]) => buildCleanSheet(elements, PAGE);

const square = [
  [100, 100],
  [300, 100],
  [300, 260],
  [100, 260],
];

describe("polygonPoints", () => {
  it("turns a pixel polygon into an SVG points list", () => {
    expect(polygonPoints(square)).toBe("100,100 300,100 300,260 100,260");
  });

  it("rejects anything that is not at least three numeric pairs", () => {
    expect(polygonPoints(undefined)).toBeNull();
    expect(polygonPoints("100,100")).toBeNull();
    expect(
      polygonPoints([
        [0, 0],
        [1, 1],
      ]),
    ).toBeNull(); // two points are a line, not an outline
    expect(polygonPoints([[0, 0], [1, 1], [2]])).toBeNull();
    expect(
      polygonPoints([
        [0, 0],
        [1, 1],
        ["2", 2],
      ]),
    ).toBeNull();
    expect(
      polygonPoints([
        [0, 0],
        [1, 1],
        [Number.NaN, 2],
      ]),
    ).toBeNull();
  });
});

describe("formatArea", () => {
  it("shows one decimal and the m² unit, like the drawings do", () => {
    expect(formatArea(28)).toBe("28.0 m²");
    expect(formatArea(12.84)).toBe("12.8 m²"); // 12.84 rounds down to 12.8
    expect(formatArea(4.75)).toBe("4.8 m²"); // 4.75 rounds half up to 4.8
  });
});

describe("buildCleanSheet", () => {
  it("draws a wall without an outline as its box", () => {
    const sheet = sheetOf([el({ id: "w1", kind: "wall", bbox: [80, 76, 1520, 96] })]);
    // The four corners of the box, clockwise from the top left.
    expect(sheet.walls).toEqual([
      { id: "w1", points: "80,76 1520,76 1520,96 80,96", added: false },
    ]);
  });

  it("draws a wall with an outline (DXF hatches) as that outline, so diagonals stay thin", () => {
    const diagonal = [
      [0, 0],
      [10, 0],
      [110, 100],
      [100, 100],
    ];
    const sheet = sheetOf([
      el({ id: "w1", kind: "wall", bbox: [0, 0, 110, 100], properties: { polygon_px: diagonal } }),
    ]);
    expect(sheet.walls[0].points).toBe("0,0 10,0 110,100 100,100");
  });

  it("skips elements without a box", () => {
    const sheet = sheetOf([
      el({ id: "w1", kind: "wall" }),
      el({ id: "r1", kind: "room", label: "OH" }),
      el({ id: "d1", kind: "door" }),
      el({ id: "t1", kind: "text", label: "NOTE" }),
    ]);
    expect(sheet).toEqual({ walls: [], rooms: [], openings: [], labels: [] });
  });

  it("gives a room its outline, its code in bold and its area underneath", () => {
    const room = el({
      id: "r1",
      kind: "room",
      label: "OH",
      name: "Living room (OH)",
      bbox: [180, 160, 220, 200], // centre (200, 180); its own height (40) is not used
      properties: { polygon_px: square, area_m2: 28 },
    });
    expect(sheetOf([room]).rooms).toEqual([
      {
        id: "r1",
        points: "100,100 300,100 300,260 100,260",
        name: "OH",
        title: "Living room (OH)",
        area: "28.0 m²",
        x: 200,
        y: 180,
        size: 15, // 1.5 × the page's text size: 1.5 × 1000 / 100
        areaY: 195, // one line below the name: 180 + 15
        areaSize: 11.25, // three quarters of the name: 0.75 × 15
        added: false,
      },
    ]);
  });

  it("keeps a room label even when its region did not close", () => {
    const room = el({
      id: "r1",
      kind: "room",
      label: "KPH",
      bbox: [0, 0, 60, 20],
      properties: { region: "not_closed" },
    });
    const [shape] = sheetOf([room]).rooms;
    expect(shape.points).toBeNull();
    expect(shape.area).toBeNull();
    expect(shape.name).toBe("KPH");
    expect(shape.title).toBe("KPH"); // no long name: the code doubles as the tooltip
  });

  it("tests printed areas against the room's outline, not its bounding box", () => {
    // An L: the 100..200 × 100..200 corner of its bounding box belongs to a neighbour.
    const ell = [
      [0, 0],
      [200, 0],
      [200, 100],
      [100, 100],
      [100, 200],
      [0, 200],
    ];
    const room = el({
      id: "r1",
      kind: "room",
      label: "OH",
      bbox: [30, 30, 70, 50],
      properties: { polygon_px: ell, area_m2: 30 },
    });
    // Centre (150, 150): inside the bounding box, outside the L, so the neighbour's.
    const neighbours = el({ id: "a1", kind: "area", label: "9.0 m2", bbox: [130, 140, 170, 160] });
    // Centre (50, 150): inside the L's lower arm, so this room prints its own.
    const own = el({ id: "a2", kind: "area", label: "30.0 m2", bbox: [30, 140, 70, 160] });
    expect(sheetOf([room, neighbours]).rooms[0].area).toBe("30.0 m²");
    const sheet = sheetOf([room, own]);
    expect(sheet.rooms[0].area).toBeNull();
    // The printed area is still drawn, as a label.
    expect(sheet.labels.map((l) => l.text)).toEqual(["30.0 m2"]);
  });

  it("draws doors and windows as uniform symbols on their boxes, with or without text", () => {
    const sheet = sheetOf([
      el({ id: "d1", kind: "door", bbox: [10, 20, 50, 60] }), // 40 × 40
      el({ id: "n1", kind: "window", label: "W2", bbox: [100, 0, 180, 8] }), // 80 × 8
    ]);
    const none = { gap: null, leaf: null, arc: null, frame: null };
    expect(sheet.openings).toEqual([
      { id: "d1", kind: "door", x: 10, y: 20, width: 40, height: 40, added: false, ...none },
      { id: "n1", kind: "window", x: 100, y: 0, width: 80, height: 8, added: false, ...none },
    ]);
    expect(sheet.labels).toEqual([]); // a symbol, not text
  });

  it("draws a door with a stored swing as its leaf and arc (D-055)", () => {
    // Gap (80, 50)..(100, 50), hinge "a", opening downwards: the leaf runs from the hinge
    // 20 px down to (80, 70); the arc, radius 20, from there back to (100, 50). From the
    // leaf (pointing down) to the gap (pointing right) is a quarter turn anticlockwise on
    // screen (y down), so the sweep flag is 0.
    const door = el({
      id: "d1",
      kind: "door",
      bbox: [80, 50, 100, 70],
      properties: { opening: { a: [80, 50], b: [100, 50] }, hinge: "a", toward: [90, 60] },
    });
    const [o] = sheetOf([door]).openings;
    expect(o.leaf).toBe("M80 50L80 70");
    expect(o.arc).toBe("M80 70A20 20 0 0 0 100 50");
    expect(o.gap).toBeNull();
  });

  it("swings a door the other way when it opens upwards from the far end", () => {
    // Hinge "b" at (100, 50), free end (80, 50), opening up: leaf to (100, 30), and from
    // there (pointing up) to the gap (pointing left) is anticlockwise again: sweep 0.
    const door = el({
      id: "d1",
      kind: "door",
      bbox: [80, 30, 100, 50],
      properties: { opening: { a: [80, 50], b: [100, 50] }, hinge: "b", toward: [90, 40] },
    });
    const [o] = sheetOf([door]).openings;
    expect(o.leaf).toBe("M100 50L100 30");
    expect(o.arc).toBe("M100 30A20 20 0 0 0 80 50");
  });

  it("draws a window by its stored frame, and an opening without a swing by its gap", () => {
    const frame = [
      [40, 44],
      [69, 44],
      [69, 48],
      [40, 48],
    ];
    const sheet = sheetOf([
      el({
        id: "n1",
        kind: "window",
        bbox: [40, 44, 69, 48],
        properties: { opening: { a: [40, 50], b: [69, 50] }, polygon_px: frame },
      }),
      el({
        id: "d1",
        kind: "door",
        bbox: [0, 0, 20, 4],
        properties: { opening: { a: [0, 2], b: [20, 2] } },
      }),
      el({ id: "d2", kind: "door", bbox: [0, 0, 20, 4], properties: { opening: { a: [0, 2] } } }),
    ]);
    expect(sheet.openings[0].frame).toBe("40,44 69,44 69,48 40,48");
    expect(sheet.openings[1]).toMatchObject({ gap: "M0 2L20 2", leaf: null, frame: null });
    expect(sheet.openings[2]).toMatchObject({ gap: null, leaf: null, frame: null }); // its box
  });

  it("marks what the upscale pass added, so it is drawn apart from what ingest found", () => {
    const added = { source: UPSCALE_SOURCE };
    const sheet = sheetOf([
      el({ id: "w1", kind: "wall", bbox: [0, 0, 100, 10], ...added }),
      el({ id: "d1", kind: "door", bbox: [0, 0, 10, 10], ...added }),
      el({ id: "r1", kind: "room", label: "WC", bbox: [0, 0, 20, 10], ...added }),
      el({ id: "w2", kind: "wall", bbox: [0, 0, 100, 10], source: "dxf" }),
    ]);
    expect(sheet.walls.map((w) => w.added)).toEqual([true, false]);
    expect(sheet.openings[0].added).toBe(true);
    expect(sheet.rooms[0].added).toBe(true);
  });

  it("hides the computed area when the drawing prints its own area inside the room", () => {
    const room = el({
      id: "r1",
      kind: "room",
      label: "OH",
      bbox: [180, 160, 220, 200],
      properties: { polygon_px: square, area_m2: 27.96 },
    });
    // Centre (200, 215) lies inside the room's extent 100..300 × 100..260.
    const printed = el({ id: "a1", kind: "area", label: "28.0 m2", bbox: [170, 205, 230, 225] });
    // Centre (400, 215) lies outside it, so it does not count.
    const elsewhere = el({ id: "a2", kind: "area", label: "9.0 m2", bbox: [370, 205, 430, 225] });
    const sheet = sheetOf([room, printed, elsewhere]);
    expect(sheet.rooms[0].area).toBeNull();
    expect(sheetOf([room, elsewhere]).rooms[0].area).toBe("28.0 m²");
  });

  it("writes every other labelled element centred on its box, all at the page's one size", () => {
    const sheet = sheetOf([
      el({ id: "d1", kind: "dimension", label: "800", bbox: [940, 840, 1000, 870] }),
      el({ id: "t1", kind: "text", text: "raw", label: null, bbox: [0, 0, 10, 10] }),
      el({ id: "s1", kind: "scale", label: "1:50", bbox: [100, 1060, 160, 1184] }),
    ]);
    // Size 1000 / 100 = 10 for all three, however tall OCR made their boxes.
    expect(sheet.labels).toEqual([
      { id: "d1", kind: "dimension", text: "800", x: 970, y: 855, size: 10 }, // centre (970, 855)
      { id: "t1", kind: "text", text: "raw", x: 5, y: 5, size: 10 }, // falls back to the raw text
      { id: "s1", kind: "scale", text: "1:50", x: 130, y: 1122, size: 10 },
    ]);
  });

  it("leaves out unclassified OCR text that is unsure or has no letter or digit", () => {
    const sheet = sheetOf([
      el({ id: "t1", kind: "text", label: "“Lae", confidence: 0.37, bbox: [0, 0, 50, 112] }),
      el({ id: "t2", kind: "text", label: "Keittiö", confidence: 0.6, bbox: [0, 0, 50, 20] }), // at the bar
      el({ id: "t3", kind: "text", label: "—.", confidence: 0.88, bbox: [0, 0, 10, 10] }),
      el({ id: "d1", kind: "dimension", label: "1100", confidence: 0.47, bbox: [0, 0, 30, 10] }),
    ]);
    // Classified kinds (dimension) are kept whatever their confidence: ingest checked them.
    expect(sheet.labels.map((l) => l.id)).toEqual(["t2", "d1"]);
  });

  it("leaves out elements with nothing to write and degenerate boxes", () => {
    const sheet = sheetOf([
      el({ id: "x1", kind: "fixture", bbox: [0, 0, 10, 10] }), // no text and not a symbol
      el({ id: "x2", kind: "text", label: "  ", bbox: [0, 0, 10, 10] }),
      el({ id: "x3", kind: "wall", bbox: [10, 10, 10, 50] }), // zero width
      el({ id: "x4", kind: "text", label: "A", bbox: [0, 10, 10, 10] }), // zero height
      el({ id: "x5", kind: "door", bbox: [0, 0, 0, 10] }), // zero width
    ]);
    expect(sheet).toEqual({ walls: [], rooms: [], openings: [], labels: [] });
  });
});

describe("scaleBar", () => {
  const page = { width: 1600, height: 1120 };

  it("picks the longest round length that fits a fifth of the page width", () => {
    // 1:50 at 200 dpi: 6.35 mm per px, so 1 m = 1000 / 6.35 ≈ 157.48 px.
    // A fifth of 1600 px is 320 px: 2 m ≈ 314.96 px fits, 5 m ≈ 787 px does not.
    const bar = scaleBar(page, 6.35);
    expect(bar?.label).toBe("2 m");
    expect(bar?.length).toBeCloseTo(314.96, 2);
  });

  it("sits in the top-left margin, sized from the page width", () => {
    const bar = scaleBar(page, 6.35);
    // size = 1600 / 100 = 16 px; margin = 2 × 16 = 32 px from the left and top edges.
    // Top, not bottom: title blocks and plan titles usually sit along the bottom.
    expect(bar).toMatchObject({ x: 32, y: 32, size: 16 });
  });

  it("drops to centimetres for very large-scale pages", () => {
    // 1 mm per px: 1 m = 1000 px is too long; 0.2 m = 200 px fits under 320 px, 0.5 m = 500 px does not.
    const bar = scaleBar(page, 1);
    expect(bar?.label).toBe("20 cm");
    expect(bar?.length).toBe(200);
  });

  it("is absent when the scale is unknown or nothing fits", () => {
    expect(scaleBar(page, null)).toBeNull();
    expect(scaleBar(page, 0)).toBeNull();
    // 0.01 mm per px: even 0.1 m = 10 000 px is wider than the page.
    expect(scaleBar(page, 0.01)).toBeNull();
  });
});
