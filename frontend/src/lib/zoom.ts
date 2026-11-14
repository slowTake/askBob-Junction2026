/** Zoom levels of the drawing viewer (1 = the sheet fits the viewer's width). */

export const ZOOMS = [1, 1.5, 2, 3, 4];
const FOCUS_MIN_ZOOM = 2;

/** The next zoom level below (`-1`) or above (`1`) `current`; stays put at either end. */
export function stepZoom(current: number, direction: -1 | 1): number {
  if (direction === 1) return ZOOMS.find((z) => z > current) ?? current;
  return [...ZOOMS].reverse().find((z) => z < current) ?? current;
}

/** Zoom to use when a citation is first focused: close enough to read the cited box. */
export function focusZoom(current: number): number {
  return Math.max(current, FOCUS_MIN_ZOOM);
}
