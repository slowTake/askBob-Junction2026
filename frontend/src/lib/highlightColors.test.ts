import { describe, expect, it } from "vitest";
import { highlightColors } from "./highlightColors";

function element(id: string, kind: string, properties = {}, label: string | null = null) {
  return { id, kind, properties, label };
}

describe("highlightColors", () => {
  it("distinguishes doors, windows and room categories while grouping the same type", () => {
    const colors = highlightColors([
      element("d1", "door"),
      element("d2", "door"),
      element("w", "window"),
      element("k", "room", { category: "kitchen" }),
      element("b", "room", { category: "bathroom" }),
    ]);
    expect(colors.get("d1")).toBe(colors.get("d2"));
    expect(new Set(colors.values()).size).toBe(4);
  });

  it("distinguishes apartments using their unit, label, or ID when metadata is missing", () => {
    const colors = highlightColors([
      element("a", "unit", { unit: "A" }),
      element("b", "unit", {}, "B"),
      element("c", "unit"),
      element("d", "unit"),
    ]);
    expect(new Set(colors.values()).size).toBe(4);
  });

  it("is independent of input order and normalizes category spelling", () => {
    const elements = [
      element("a", "room", { category: " Kitchen " }),
      element("b", "room", { category: "kitchen" }),
      element("w", "window"),
    ];
    const colors = highlightColors(elements);
    expect(colors.get("a")).toBe(colors.get("b"));
    expect(highlightColors([...elements].reverse())).toEqual(colors);
  });

  it("handles empty pages and missing or malformed categories", () => {
    expect(highlightColors([]).size).toBe(0);
    const colors = highlightColors([element("a", "room"), element("b", "room", { category: 42 })]);
    expect(colors.get("a")).toBe(colors.get("b"));
  });

  it("continues assigning distinct colors beyond the fixed palette", () => {
    const elements = Array.from({ length: 30 }, (_, i) => element(`u${i}`, "unit"));
    expect(new Set(highlightColors(elements).values()).size).toBe(elements.length);
  });
});
