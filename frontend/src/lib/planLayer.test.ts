import { describe as group, expect, it } from "vitest";
import type { ElementInfo } from "../api/types";
import { describe, drawOrder, extentBox, layerOf, shapeOf, unionBox } from "./planLayer";

function el(over: Partial<ElementInfo>): ElementInfo {
  return {
    id: "e",
    document_id: "d",
    page_id: "p",
    kind: "room",
    text: null,
    label: null,
    name: null,
    value_mm: null,
    bbox: [10, 20, 50, 80],
    ifc_guid: null,
    properties: {},
    source: "dxf",
    confidence: 1,
    ...over,
  };
}

group("planLayer", () => {
  it("assigns kinds to layers", () => {
    expect(layerOf("door")).toBe("openings");
    expect(layerOf("room_number")).toBe("labels");
    expect(layerOf("height")).toBe("labels"); // "h1600" ceiling heights (#36)
    expect(layerOf("storey")).toBeNull();
  });

  it("uses the room outline when present, else the box", () => {
    const outline = el({
      properties: {
        polygon_px: [
          [0, 0],
          [10, 0],
          [10, 5],
        ],
      },
    });
    expect(shapeOf(outline)).toEqual({ type: "polygon", points: "0,0 10,0 10,5" });
    // bbox [10, 20, 50, 80] -> x 10, y 20, 40 wide, 60 high
    expect(shapeOf(el({}))).toEqual({ type: "rect", x: 10, y: 20, width: 40, height: 60 });
    expect(shapeOf(el({ bbox: null }))).toBeNull();
  });

  it("draws apartments, then rooms, then everything else", () => {
    const order = drawOrder([
      el({ id: "d", kind: "door" }),
      el({ id: "r" }),
      el({ id: "u", kind: "unit" }),
    ]);
    expect(order.map((e) => e.id)).toEqual(["u", "r", "d"]);
  });

  it("describes a room and a door", () => {
    const room = el({
      text: "Zimmer",
      name: "room (Zimmer) 2.01",
      properties: { number: "2.01", area_m2: 15.61, unit: "A" },
    });
    expect(describe(room)).toEqual({
      title: "Zimmer",
      details: ["room (Zimmer) 2.01", "No. 2.01", "15.61 m²", "Apartment A", "dxf"],
    });
    const door = el({ kind: "door", label: "09", value_mm: 900, source: "ocr", confidence: 0.62 });
    expect(describe(door).details).toEqual(["900 mm wide", "ocr, 62% sure"]);
  });
});

group("unionBox", () => {
  it("frames the chosen elements only", () => {
    const els = [
      el({ id: "a", bbox: [0, 0, 10, 10] }),
      el({ id: "b", bbox: [20, 5, 30, 40] }),
      el({ id: "c", bbox: [100, 100, 110, 110] }),
    ];
    expect(unionBox(els, new Set(["a", "b"]))).toEqual([0, 0, 30, 40]);
    expect(unionBox(els, new Set(["zzz"]))).toBeNull();
  });

  it("frames a room by its outline, not by its printed name (#70)", () => {
    // Name box [500,390,539,424] inside the outline x 400..700, y 300..500.
    const room = el({ id: "r", bbox: [500, 390, 539, 424], properties: { polygon_px: SQUARE } });
    expect(unionBox([room], new Set(["r"]))).toEqual([400, 300, 700, 500]);
  });
});

const SQUARE = [
  [400, 300],
  [700, 300],
  [700, 500],
  [400, 500],
];

group("extentBox", () => {
  it("is the outline's bounds when there is one, else the box", () => {
    expect(
      extentBox(el({ bbox: [500, 390, 539, 424], properties: { polygon_px: SQUARE } })),
    ).toEqual([400, 300, 700, 500]);
    expect(extentBox(el({ bbox: [1, 2, 3, 4] }))).toEqual([1, 2, 3, 4]);
    expect(extentBox(el({ bbox: null }))).toBeNull();
  });
});
