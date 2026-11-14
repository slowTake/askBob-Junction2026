import { describe, expect, it } from "vitest";
import type { Citation, ElementInfo, PlanView } from "../api/types";
import type { BBox } from "./camera";
import { onPage, readingOrder } from "./target";

function el(id: string, bbox: BBox | null): ElementInfo {
  return {
    id,
    document_id: "d",
    page_id: "p",
    kind: "window",
    text: null,
    label: null,
    name: null,
    value_mm: null,
    bbox,
    ifc_guid: null,
    properties: {},
    source: "dxf",
    confidence: 1,
  };
}

const view = (over: Partial<PlanView> = {}): PlanView => ({
  document_id: "d",
  page_id: "p",
  page_index: 0,
  element_ids: ["a", "b"],
  line: null,
  caption: null,
  ...over,
});

const citation = (over: Partial<Citation> = {}): Citation => ({
  element_id: "a",
  document_id: "d",
  page_id: "p",
  page_index: 0,
  bbox: [10, 20, 30, 40],
  ifc_guid: null,
  polygon: null,
  label_bbox: null,
  target: "element",
  note: "Door tag 09",
  verified: true,
  ...over,
});

const elements = [el("a", [100, 100, 120, 110]), el("b", [500, 300, 540, 320]), el("c", null)];

describe("onPage, for an agent view", () => {
  it("lights up its elements and frames all of them", () => {
    expect(onPage({ kind: "view", view: view() }, 0, elements)).toMatchObject({
      highlightIds: ["a", "b"],
      frame: [100, 100, 540, 320], // union of a and b
      spotlight: null,
      caption: "2 elements",
    });
  });

  it("frames a measured line with its end points", () => {
    const line = { from: [110, 105] as [number, number], to: [900, 700] as [number, number] };
    const shown = onPage(
      { kind: "view", view: view({ line: { ...line, label: "8.40 m" } }) },
      0,
      elements,
    );
    expect(shown?.frame).toEqual([100, 100, 900, 700]);
    expect(shown?.caption).toBe("8.40 m");
  });

  it("uses the agent's caption when it gave one", () => {
    const shown = onPage({ kind: "view", view: view({ caption: "Bedrooms" }) }, 0, elements);
    expect(shown?.caption).toBe("Bedrooms");
  });

  it("shows nothing on another page", () => {
    expect(onPage({ kind: "view", view: view() }, 1, elements)).toBeNull();
  });
});

describe("onPage, for a citation", () => {
  it("spotlights and frames the cited box", () => {
    expect(onPage({ kind: "citation", citation: citation() }, 0, elements)).toMatchObject({
      highlightIds: ["a"],
      spotlight: [10, 20, 30, 40],
      frame: [10, 20, 30, 40],
      caption: "Door tag 09",
      verified: true,
    });
  });

  it("shows nothing on another page", () => {
    expect(onPage({ kind: "citation", citation: citation() }, 3, elements)).toBeNull();
  });

  it("spotlights a room's outline when the citation has one (#70)", () => {
    const polygon = [
      [400, 300],
      [700, 300],
      [700, 500],
      [400, 500],
    ];
    const room = citation({ bbox: [400, 300, 700, 500], polygon });
    expect(onPage({ kind: "citation", citation: room }, 0, elements)).toMatchObject({
      spotlight: [400, 300, 700, 500],
      spotlightPolygon: polygon,
      frame: [400, 300, 700, 500],
    });
    expect(onPage({ kind: "citation", citation: citation() }, 0, elements)?.spotlightPolygon).toBe(
      null,
    );
  });

  it("says when only a room's printed name could be marked (#70)", () => {
    const named = citation({ target: "label" });
    expect(onPage({ kind: "citation", citation: named }, 0, elements)?.labelOnly).toBe(true);
    expect(onPage({ kind: "citation", citation: citation() }, 0, elements)?.labelOnly).toBe(false);
  });
});

describe("readingOrder", () => {
  it("numbers highlighted elements top to bottom, then left to right", () => {
    const grid = [
      el("right-top", [500, 100, 520, 110]),
      el("left-bottom", [100, 400, 120, 410]),
      el("left-top", [100, 100, 120, 110]),
      el("not-lit", [0, 0, 10, 10]),
    ];
    const lit = new Set(["right-top", "left-bottom", "left-top"]);
    expect(readingOrder(grid, lit).map((e) => e.id)).toEqual([
      "left-top",
      "right-top",
      "left-bottom",
    ]);
  });

  it("frames a walked route and keeps its points and label (plan answers)", () => {
    const path = {
      points: [
        [100, 100],
        [400, 120],
        [420, 600],
      ] as [number, number][],
      label: "12.3 m",
    };
    const shown = onPage({ kind: "view", view: view({ element_ids: [], path }) }, 0, []);
    expect(shown?.path).toEqual(path);
    expect(shown?.frame).toEqual([100, 100, 420, 600]);
    expect(shown?.caption).toBe("12.3 m");
    expect(shown?.highlightIds).toEqual([]);
  });

  it("carries labels to write on the plan, and frames them", () => {
    const labels = [{ at: [300, 200] as [number, number], text: "Apartment A · 78.4 m²" }];
    const shown = onPage({ kind: "view", view: view({ element_ids: [], labels }) }, 0, []);
    expect(shown?.labels).toEqual(labels);
    expect(shown?.frame).toEqual([300, 200, 300, 200]);
  });

  it("reads views cached before routes and labels existed", () => {
    const shown = onPage({ kind: "view", view: view() }, 0, [el("a", [0, 0, 10, 10])]);
    expect(shown?.labels).toEqual([]);
    expect(shown?.path).toBeNull();
  });
});
