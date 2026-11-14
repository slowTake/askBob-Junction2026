import { describe, expect, it } from "vitest";
import {
  buildCleanSheet,
  formatArea,
  hasEnoughForClean,
  MIN_WALLS,
  polygonPoints,
  scaleBar,
  type RedrawElement,
} from "./redraw";

function el(over: Partial<RedrawElement> & Pick<RedrawElement, "id" | "kind">): RedrawElement {
  return { bbox: null, label: null, name: null, text: null, properties: {}, ...over };
}

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
  it("draws walls as filled rectangles from their boxes", () => {
    const sheet = buildCleanSheet([el({ id: "w1", kind: "wall", bbox: [80, 76, 1520, 96] })]);
    // width 1520 − 80 = 1440, height 96 − 76 = 20
    expect(sheet.walls).toEqual([{ id: "w1", x: 80, y: 76, width: 1440, height: 20 }]);
  });

  it("skips elements without a box", () => {
    const sheet = buildCleanSheet([
      el({ id: "w1", kind: "wall" }),
      el({ id: "r1", kind: "room", label: "OH" }),
      el({ id: "t1", kind: "text", label: "NOTE" }),
    ]);
    expect(sheet).toEqual({ walls: [], rooms: [], labels: [] });
  });

  it("gives a room its outline, its code in bold and its area underneath", () => {
    const room = el({
      id: "r1",
      kind: "room",
      label: "OH",
      name: "Living room (OH)",
      bbox: [180, 160, 220, 200], // centre (200, 180), height 40
      properties: { polygon_px: square, area_m2: 28 },
    });
    expect(buildCleanSheet([room]).rooms).toEqual([
      {
        id: "r1",
        points: "100,100 300,100 300,260 100,260",
        name: "OH",
        title: "Living room (OH)",
        area: "28.0 m²",
        x: 200,
        y: 180,
        size: 40,
        areaY: 220, // one line below the name: 180 + 40
        areaSize: 30, // three quarters of the name: 0.75 × 40
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
    const [shape] = buildCleanSheet([room]).rooms;
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
    expect(buildCleanSheet([room, neighbours]).rooms[0].area).toBe("30.0 m²");
    const sheet = buildCleanSheet([room, own]);
    expect(sheet.rooms[0].area).toBeNull();
    // The printed area is still drawn, as a label.
    expect(sheet.labels.map((l) => l.text)).toEqual(["30.0 m2"]);
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
    const sheet = buildCleanSheet([room, printed, elsewhere]);
    expect(sheet.rooms[0].area).toBeNull();
    expect(buildCleanSheet([room, elsewhere]).rooms[0].area).toBe("28.0 m²");
  });

  it("writes every other labelled element as text centred on its box, sized by its height", () => {
    const sheet = buildCleanSheet([
      el({ id: "d1", kind: "dimension", label: "800", bbox: [940, 840, 1000, 870] }),
      el({ id: "t1", kind: "text", text: "raw", label: null, bbox: [0, 0, 10, 10] }),
      el({ id: "s1", kind: "scale", label: "1:50", bbox: [100, 1060, 160, 1084] }),
    ]);
    expect(sheet.labels).toEqual([
      { id: "d1", kind: "dimension", text: "800", x: 970, y: 855, size: 30 }, // centre (970, 855), height 30
      { id: "t1", kind: "text", text: "raw", x: 5, y: 5, size: 10 }, // falls back to the raw text
      { id: "s1", kind: "scale", text: "1:50", x: 130, y: 1072, size: 24 },
    ]);
  });

  it("leaves out elements with nothing to write and degenerate boxes", () => {
    const sheet = buildCleanSheet([
      el({ id: "x1", kind: "door", bbox: [0, 0, 10, 10] }), // a symbol without text
      el({ id: "x2", kind: "text", label: "  ", bbox: [0, 0, 10, 10] }),
      el({ id: "x3", kind: "wall", bbox: [10, 10, 10, 50] }), // zero width
      el({ id: "x4", kind: "text", label: "A", bbox: [0, 10, 10, 10] }), // zero height
    ]);
    expect(sheet).toEqual({ walls: [], rooms: [], labels: [] });
  });
});

describe("hasEnoughForClean", () => {
  const wall = (id: string) => el({ id, kind: "wall", bbox: [0, 0, 100, 10] });

  it(`needs at least ${MIN_WALLS} walls`, () => {
    expect(MIN_WALLS).toBe(3);
    expect(hasEnoughForClean(buildCleanSheet([wall("1"), wall("2")]))).toBe(false);
    expect(hasEnoughForClean(buildCleanSheet([wall("1"), wall("2"), wall("3")]))).toBe(true);
  });

  it("is false for a page of text alone, however much text", () => {
    const texts = Array.from({ length: 50 }, (_, i) =>
      el({ id: `t${i}`, kind: "text", label: "x", bbox: [0, 0, 10, 10] }),
    );
    expect(hasEnoughForClean(buildCleanSheet(texts))).toBe(false);
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
