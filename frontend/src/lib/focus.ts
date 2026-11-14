/** Which part of a focused citation belongs on the page being shown. */

import type { BBox } from "./viewport";

export interface FocusTarget {
  page_index: number | null;
  bbox: BBox | null;
}

/** The box to spotlight: only on the page the citation points at. */
export function focusBox(focus: FocusTarget | null, pageIndex: number): BBox | null {
  return focus !== null && focus.page_index === pageIndex ? focus.bbox : null;
}

/** Whether the citation's banner belongs on this page (unknown pages keep their note). */
export function focusIsHere(focus: FocusTarget | null, pageIndex: number): boolean {
  return focus !== null && (focus.page_index === null || focus.page_index === pageIndex);
}
