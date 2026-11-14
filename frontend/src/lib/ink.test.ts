import { describe, expect, it } from "vitest";
import { inkBox, luminance, toPageBox } from "./ink";

/** A white `width` x `height` luminance image with dark (0) pixels where `dark` says. */
function image(width: number, height: number, dark: (x: number, y: number) => boolean) {
  const lum = new Uint8ClampedArray(width * height).fill(255);
  for (let y = 0; y < height; y++)
    for (let x = 0; x < width; x++) if (dark(x, y)) lum[y * width + x] = 0;
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
    // ink in columns 2..5 and rows 3..6 -> [2, 3, 6, 7]
    const lum = image(10, 10, (x, y) => x >= 2 && x <= 5 && y >= 3 && y <= 6);
    expect(inkBox(lum, 10, 10)).toEqual([2, 3, 6, 7]);
  });

  it("ignores a lone speck far from the drawing", () => {
    // 20 x 20 square at 10..29 (400 dark pixels) plus one speck at (0, 0): 401 in all.
    // 0.5% of 401 = 2.005, so the speck's single pixel on each axis is trimmed.
    const lum = image(
      40,
      40,
      (x, y) => (x === 0 && y === 0) || (x >= 10 && x < 30 && y >= 10 && y < 30),
    );
    expect(inkBox(lum, 40, 40)).toEqual([10, 10, 30, 30]);
  });

  it("keeps a thin outer line of the drawing", () => {
    // A 1 px frame around 5..34: each side is 30 px of ink, far above 0.5% of 116.
    const frame = (x: number, y: number) =>
      x >= 5 && x < 35 && y >= 5 && y < 35 && (x === 5 || x === 34 || y === 5 || y === 34);
    expect(inkBox(image(40, 40, frame), 40, 40)).toEqual([5, 5, 35, 35]);
  });

  it("does not count light paper tones as ink", () => {
    const lum = new Uint8ClampedArray(16).fill(200); // greyish paper, above the ink threshold
    expect(inkBox(lum, 4, 4)).toBeNull();
  });

  it("is null for a blank page", () => {
    expect(
      inkBox(
        image(5, 5, () => false),
        5,
        5,
      ),
    ).toBeNull();
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
