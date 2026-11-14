import { describe, expect, it } from "vitest";
import { focusZoom, stepZoom, ZOOMS } from "./zoom";

describe("stepZoom", () => {
  it("moves one step down and up through the fixed zoom levels", () => {
    expect(ZOOMS).toEqual([1, 1.5, 2, 3, 4]);
    expect(stepZoom(2, -1)).toBe(1.5); // 200 % -> 150 %, the step that was stuck in #8
    expect(stepZoom(1.5, -1)).toBe(1);
    expect(stepZoom(2, 1)).toBe(3);
  });

  it("stops at the ends", () => {
    expect(stepZoom(1, -1)).toBe(1);
    expect(stepZoom(4, 1)).toBe(4);
  });

  it("snaps a value between two levels to the next level in that direction", () => {
    expect(stepZoom(2.5, -1)).toBe(2);
    expect(stepZoom(2.5, 1)).toBe(3);
  });
});

describe("focusZoom", () => {
  it("zooms in to at least 200 % for a cited box", () => {
    expect(focusZoom(1)).toBe(2);
    expect(focusZoom(1.5)).toBe(2);
  });

  it("keeps a closer zoom the user already chose", () => {
    expect(focusZoom(3)).toBe(3);
  });
});
