/** Where the drawing is on a page image: the box around its ink (#83). Pure: the caller
 * samples the image (see useInkBox) and passes the pixels in. */

import type { BBox, Size } from "./camera";

// Luminance (0..255) below this is ink. Paper, even on greyish scans, is lighter; thin lines
// get paler when the image is sampled down, so the threshold sits well above black.
const INK = 200;
// Ink is grouped in cells this many sample px wide, joined to touching cells: pieces 8 px
// (two cells) or more apart are always separate, closer ones may join.
const CELL = 4;
const KEEP = 0.1; // pieces with less ink than this share of the largest are not the drawing

/** RGBA pixels (canvas ImageData) to luminance. Transparent pixels read as white paper. */
export function luminance(rgba: ArrayLike<number>): Uint8ClampedArray {
  const lum = new Uint8ClampedArray(rgba.length / 4);
  for (let i = 0; i < lum.length; i++) {
    const [r, g, b, a] = [rgba[4 * i], rgba[4 * i + 1], rgba[4 * i + 2], rgba[4 * i + 3]];
    lum[i] = a < 128 ? 255 : Math.round(0.299 * r + 0.587 * g + 0.114 * b);
  }
  return lum;
}

interface Piece {
  ink: number;
  box: BBox; // x0, y0, x1, y1 in sample px, end exclusive
}

/**
 * The box around the drawing in a `width` x `height` luminance image, end exclusive, or
 * null on a blank page. Ink is split into connected pieces; the drawing is every piece
 * with at least KEEP of the largest piece's ink. Logos, footers, page numbers and specks
 * set apart from the plan are small pieces and drop out; several floor plans on one
 * sheet are all kept.
 */
export function inkBox(lum: ArrayLike<number>, width: number, height: number): BBox | null {
  const pieces = inkPieces(lum, width, height);
  if (pieces.length === 0) return null;
  const largest = Math.max(...pieces.map((p) => p.ink));
  return pieces
    .filter((p) => p.ink >= KEEP * largest)
    .map((p) => p.box)
    .reduce((a, b) => [
      Math.min(a[0], b[0]),
      Math.min(a[1], b[1]),
      Math.max(a[2], b[2]),
      Math.max(a[3], b[3]),
    ]);
}

/** A box in the sampled image to page pixels. */
export function toPageBox(box: BBox, sample: Size, page: Size): BBox {
  const sx = page.width / sample.width;
  const sy = page.height / sample.height;
  return [box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy];
}

/** Connected pieces of ink: cells holding ink, joined to their eight neighbours. */
function inkPieces(lum: ArrayLike<number>, width: number, height: number): Piece[] {
  const cw = Math.ceil(width / CELL);
  const ch = Math.ceil(height / CELL);
  const cells: (Piece | null)[] = new Array(cw * ch).fill(null);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (lum[y * width + x] >= INK) continue;
      const i = Math.floor(y / CELL) * cw + Math.floor(x / CELL);
      const cell = cells[i];
      if (cell) {
        // In place: this runs for every dark pixel, so no new arrays (PR #92 review).
        cell.ink++;
        grow(cell.box, x, y, x + 1, y + 1);
      } else cells[i] = { ink: 1, box: [x, y, x + 1, y + 1] };
    }
  }

  const seen = new Uint8Array(cw * ch);
  const pieces: Piece[] = [];
  for (let start = 0; start < cells.length; start++) {
    if (!cells[start] || seen[start]) continue;
    const piece: Piece = { ink: 0, box: [width, height, 0, 0] };
    const stack = [start];
    seen[start] = 1;
    while (stack.length > 0) {
      const i = stack.pop() as number;
      const cell = cells[i] as Piece;
      piece.ink += cell.ink;
      grow(piece.box, ...cell.box);
      const cx = i % cw;
      const cy = (i - cx) / cw;
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          const nx = cx + dx;
          const ny = cy + dy;
          if (nx < 0 || ny < 0 || nx >= cw || ny >= ch) continue;
          const n = ny * cw + nx;
          if (cells[n] && !seen[n]) {
            seen[n] = 1;
            stack.push(n);
          }
        }
      }
    }
    pieces.push(piece);
  }
  return pieces;
}

/** Widen `box` in place to cover x0..x1, y0..y1. */
function grow(box: BBox, x0: number, y0: number, x1: number, y1: number): void {
  if (x0 < box[0]) box[0] = x0;
  if (y0 < box[1]) box[1] = y0;
  if (x1 > box[2]) box[2] = x1;
  if (y1 > box[3]) box[3] = y1;
}
