/** Where the drawing is on a page image: the box around its ink (#83). Pure: the caller
 * samples the image (see useInkBox) and passes the pixels in. */

import type { BBox, Size } from "./camera";

// Luminance (0..255) below this is ink. Paper, even on greyish scans, is lighter; thin lines
// get paler when the image is sampled down, so the threshold sits well above black.
const INK = 200;
const TRIM = 0.005; // share of the ink trimmed from each side, so lone specks don't count

/** RGBA pixels (canvas ImageData) to luminance. Transparent pixels read as white paper. */
export function luminance(rgba: ArrayLike<number>): Uint8ClampedArray {
  const lum = new Uint8ClampedArray(rgba.length / 4);
  for (let i = 0; i < lum.length; i++) {
    const [r, g, b, a] = [rgba[4 * i], rgba[4 * i + 1], rgba[4 * i + 2], rgba[4 * i + 3]];
    lum[i] = a < 128 ? 255 : Math.round(0.299 * r + 0.587 * g + 0.114 * b);
  }
  return lum;
}

/**
 * The box around the ink of a `width` x `height` luminance image, end exclusive, or null
 * on a blank page. Each side drops the first TRIM of the ink counted from that side:
 * a speck has almost no ink, while even a thin line of the drawing has plenty.
 */
export function inkBox(lum: ArrayLike<number>, width: number, height: number): BBox | null {
  const cols = new Array<number>(width).fill(0);
  const rows = new Array<number>(height).fill(0);
  let total = 0;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (lum[y * width + x] < INK) {
        cols[x]++;
        rows[y]++;
        total++;
      }
    }
  }
  if (total === 0) return null;
  const cut = TRIM * total;
  return [first(cols, cut), first(rows, cut), last(cols, cut) + 1, last(rows, cut) + 1];
}

/** A box in the sampled image to page pixels. */
export function toPageBox(box: BBox, sample: Size, page: Size): BBox {
  const sx = page.width / sample.width;
  const sy = page.height / sample.height;
  return [box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy];
}

/** First index where the running count passes `cut`. */
function first(counts: number[], cut: number): number {
  let sum = 0;
  for (let i = 0; i < counts.length; i++) {
    sum += counts[i];
    if (sum > cut) return i;
  }
  return counts.length - 1;
}

/** Last index where the running count from the end passes `cut`. */
function last(counts: number[], cut: number): number {
  let sum = 0;
  for (let i = counts.length - 1; i >= 0; i--) {
    sum += counts[i];
    if (sum > cut) return i;
  }
  return 0;
}
