import { describe, expect, it } from "vitest";
import { inkBox, luminance, toPageBox } from "./ink";

type Rect = [number, number, number, number]; // x0, y0, x1, y1, end exclusive

/** A white `width` x `height` luminance image with black rectangles. */
function image(width: number, height: number, rects: Rect[]) {
  const lum = new Uint8ClampedArray(width * height).fill(255);
  for (const [x0, y0, x1, y1] of rects)
    for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) lum[y * width + x] = 0;
  return lum;
}

describe("luminance", () => {
  it("weights red, green and blue like the eye, and reads transparency as paper", () => {
    // 0.299*255 = 76.2 -> 76; 0.587*255 = 149.7 -> 150; 0.114*255 = 29.1 -> 29
    const rgba = [255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 0, 0, 0, 0];
    expect(Array.from(luminance(rgba))).toEqual([76, 150, 29, 255]);
  });
});

describe("inkBox", () => {
  it("is the box around the dark pixels, end exclusive", () => {
    expect(inkBox(image(10, 10, [[2, 3, 6, 7]]), 10, 10)).toEqual([2, 3, 6, 7]);
  });

  it("ignores a lone speck far from the drawing", () => {
    // The 20 x 20 drawing has 400 dark pixels; the speck at (0, 0) has 1, under 10% of it.
    const lum = image(40, 40, [
      [0, 0, 1, 1],
      [10, 10, 30, 30],
    ]);
    expect(inkBox(lum, 40, 40)).toEqual([10, 10, 30, 30]);
  });

  it("ignores a logo and a footer line set apart from the plan (colorful-268)", () => {
    // Plan: 40 x 40 at x 50..89, y 5..44 = 1600 px. Logo 8 x 8 = 64 px bottom left;
    // footer 30 x 2 = 60 px under the plan, 9 px below it (rows 45..53 are blank; pieces
    // 8+ px apart are always separate). Both are under 10% of 1600.
    const lum = image(100, 60, [
      [50, 5, 90, 45],
      [2, 50, 10, 58],
      [55, 54, 85, 56],
    ]);
    expect(inkBox(lum, 100, 60)).toEqual([50, 5, 90, 45]);
  });

  it("keeps every floor plan on a sheet with several", () => {
    // Two 20 x 20 plans, 35 px apart: equal ink, so both count; the box spans them.
    const lum = image(90, 40, [
      [5, 10, 25, 30],
      [60, 10, 80, 30],
    ]);
    expect(inkBox(lum, 90, 40)).toEqual([5, 10, 80, 30]);
  });

  it("keeps a thin outer line of the drawing", () => {
    // A 1 px frame around 5..34: one connected piece.
    const frame: Rect[] = [
      [5, 5, 35, 6],
      [5, 34, 35, 35],
      [5, 5, 6, 35],
      [34, 5, 35, 35],
    ];
    expect(inkBox(image(40, 40, frame), 40, 40)).toEqual([5, 5, 35, 35]);
  });

  it("does not count light paper tones as ink", () => {
    const lum = new Uint8ClampedArray(16).fill(200); // greyish paper, above the ink threshold
    expect(inkBox(lum, 4, 4)).toBeNull();
  });

  it("is null for a blank page", () => {
    expect(inkBox(image(5, 5, []), 5, 5)).toBeNull();
  });
});

describe("toPageBox", () => {
  it("scales a box from the sampled image to page pixels", () => {
    // x: 1000 / 10 = 100 per sample px; y: 500 / 10 = 50
    expect(
      toPageBox([2, 3, 6, 7], { width: 10, height: 10 }, { width: 1000, height: 500 }),
    ).toEqual([200, 150, 600, 350]);
  });
});
