/** Geometry for scrolling a zoomed drawing so a cited box sits in the middle. */

export type BBox = [number, number, number, number];

export interface Size {
  width: number;
  height: number;
}

/**
 * Scroll offsets that centre `bbox` (page pixels) in a viewport showing the page at
 * `displayedWidth` CSS pixels wide. Clamped so we never scroll past the page edges.
 */
export function scrollToCenter(
  bbox: BBox,
  page: Size,
  displayedWidth: number,
  viewport: Size,
): { left: number; top: number } {
  const scale = displayedWidth / page.width;
  const cx = ((bbox[0] + bbox[2]) / 2) * scale;
  const cy = ((bbox[1] + bbox[3]) / 2) * scale;
  const maxLeft = Math.max(0, displayedWidth - viewport.width);
  const maxTop = Math.max(0, page.height * scale - viewport.height);
  return {
    left: clamp(cx - viewport.width / 2, 0, maxLeft),
    top: clamp(cy - viewport.height / 2, 0, maxTop),
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
