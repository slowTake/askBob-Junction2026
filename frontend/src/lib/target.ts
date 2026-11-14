/** What the plan shows on request: an agent view, or one cited source. */

import type { Citation, ElementInfo, PlanView } from "../api/types";
import type { BBox } from "./camera";
import { unionBox } from "./planLayer";

export type PlanTarget =
  { kind: "view"; view: PlanView } | { kind: "citation"; citation: Citation };

export interface TargetOnPage {
  highlightIds: string[];
  spotlight: BBox | null; // a cited region: everything else is dimmed
  spotlightPolygon: number[][] | null; // the cited room's outline, cut out instead of the box
  frame: BBox | null; // what the camera moves to
  line: PlanView["line"];
  caption: string;
  verified: boolean | null; // citations only
  labelOnly: boolean; // a room whose outline is unknown: only its printed name is marked
}

export function targetDocument(target: PlanTarget): string | null {
  return target.kind === "view" ? target.view.document_id : target.citation.document_id;
}

export function targetPage(target: PlanTarget): number | null {
  return target.kind === "view" ? target.view.page_index : target.citation.page_index;
}

/** The target's part on page `pageIndex`, or null when it is about another page. */
export function onPage(
  target: PlanTarget | null,
  pageIndex: number,
  elements: ElementInfo[],
): TargetOnPage | null {
  if (target === null || targetPage(target) !== pageIndex) return null;
  if (target.kind === "citation") {
    const c = target.citation;
    return {
      highlightIds: c.element_id ? [c.element_id] : [],
      spotlight: c.bbox,
      spotlightPolygon: c.polygon,
      frame: c.bbox,
      line: null,
      caption: c.note || "Cited source",
      verified: c.verified,
      labelOnly: c.target === "label",
    };
  }
  const { element_ids: ids, line, caption } = target.view;
  const boxes = unionBox(elements, new Set(ids));
  const ends: BBox | null = line
    ? [
        Math.min(line.from[0], line.to[0]),
        Math.min(line.from[1], line.to[1]),
        Math.max(line.from[0], line.to[0]),
        Math.max(line.from[1], line.to[1]),
      ]
    : null;
  return {
    highlightIds: ids,
    spotlight: null,
    spotlightPolygon: null,
    frame: union(boxes, ends),
    line,
    caption: caption ?? line?.label ?? `${ids.length} element${ids.length === 1 ? "" : "s"}`,
    verified: null,
    labelOnly: false,
  };
}

/** Highlighted elements in reading order (top to bottom, then left to right), for numbering. */
export function readingOrder(elements: ElementInfo[], lit: Set<string>): ElementInfo[] {
  return elements
    .filter((e) => lit.has(e.id) && e.bbox)
    .sort(
      (a, b) =>
        (a.bbox as BBox)[1] - (b.bbox as BBox)[1] || (a.bbox as BBox)[0] - (b.bbox as BBox)[0],
    );
}

function union(a: BBox | null, b: BBox | null): BBox | null {
  if (!a || !b) return a ?? b;
  return [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])];
}
