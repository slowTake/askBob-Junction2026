import { describe as group, expect, it } from "vitest";
import type { ElementInfo } from "../api/types";
import { aboutLabel, selectElement } from "./selection";

const el = (id: string, kind = "room", text: string | null = id): ElementInfo => ({
  id,
  document_id: "d1",
  page_id: "p1",
  kind,
  text,
  label: null,
  name: null,
  value_mm: null,
  bbox: null,
  ifc_guid: null,
  properties: {},
  source: "ocr",
  confidence: 1,
});

const [a, b, c] = [el("A"), el("B"), el("C")];

group("selectElement", () => {
  it("a plain click selects only that element, and clicking it again deselects it", () => {
    expect(selectElement([], a, false)).toEqual([a]);
    expect(selectElement([a, b], c, false)).toEqual([c]);
    expect(selectElement([a], a, false)).toEqual([]);
  });

  it("Shift+click adds an element, or removes it if it is already selected", () => {
    expect(selectElement([a], b, true)).toEqual([a, b]);
    expect(selectElement([a, b, c], b, true)).toEqual([a, c]);
  });

  it("a plain click on one of several selected keeps just that one", () => {
    expect(selectElement([a, b], a, false)).toEqual([a]);
  });

  it("clicking the empty plan clears the selection, unless Shift is held", () => {
    expect(selectElement([a, b], null, false)).toEqual([]);
    expect(selectElement([a, b], null, true)).toEqual([a, b]);
  });
});

group("aboutLabel", () => {
  it("names one element like before: its kind, then its name", () => {
    expect(aboutLabel([el("e1", "room", "Kitchen")])).toBe("room Kitchen");
    expect(aboutLabel([el("e2", "room_number", "101")])).toBe("room number 101");
  });

  it("counts several and lists their names", () => {
    const rooms = [el("e1", "room", "Kitchen"), el("e2", "room", "WC"), el("e3", "door", "D1")];
    expect(aboutLabel(rooms)).toBe("3 elements: Kitchen, WC, D1");
  });

  it("is null for an empty selection", () => {
    expect(aboutLabel([])).toBeNull();
  });
});
