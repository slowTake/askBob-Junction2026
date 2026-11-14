import { describe, expect, it } from "vitest";
import { focusBox, focusIsHere } from "./focus";

const onPageOne = { page_index: 0, bbox: [500, 390, 539, 424] as [number, number, number, number] };

describe("focusBox", () => {
  it("returns the cited box on the page the citation points at", () => {
    expect(focusBox(onPageOne, 0)).toEqual([500, 390, 539, 424]);
  });

  it("returns nothing on any other page", () => {
    // Citation on page 1 (index 0), viewer paged to page 2 (index 1): no spotlight (#7).
    expect(focusBox(onPageOne, 1)).toBeNull();
  });

  it("returns nothing without a citation, a box or a known page", () => {
    expect(focusBox(null, 0)).toBeNull();
    expect(focusBox({ page_index: 0, bbox: null }, 0)).toBeNull();
    expect(focusBox({ page_index: null, bbox: [1, 2, 3, 4] }, 0)).toBeNull();
  });
});

describe("focusIsHere", () => {
  it("is true on the cited page and false on other pages", () => {
    expect(focusIsHere(onPageOne, 0)).toBe(true);
    expect(focusIsHere(onPageOne, 1)).toBe(false);
  });

  it("is true for a citation whose page is unknown, so its note stays visible", () => {
    expect(focusIsHere({ page_index: null, bbox: null }, 3)).toBe(true);
  });

  it("is false without a citation", () => {
    expect(focusIsHere(null, 0)).toBe(false);
  });
});
