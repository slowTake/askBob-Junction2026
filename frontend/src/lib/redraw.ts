/**
 * The clean redraw of a drawing page (#54): extracted elements become simple shapes in
 * the page's own pixel coordinates, so anything placed on the original (citations,
 * highlights) lands on the same spot here.
 */

import type { BBox, Size } from "./viewport";

/** The fields of an extracted element (`ElementInfo`) the redraw reads. */
export interface RedrawElement {
  id: string;
  kind: string;
  bbox: BBox | null;
  label: string | null;
  name: string | null;
  text: string | null;
  properties: Record<string, unknown>;
}

export interface WallShape {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface RoomShape {
  id: string;
  /** SVG `points` of the room outline, or null when its region did not close. */
  points: string | null;
  /** The code as printed (bold); `title` is the long name for the tooltip. */
  name: string;
  title: string;
  /** Computed area, or null when unknown or the drawing prints its own. */
  area: string | null;
  x: number;
  y: number;
  size: number;
  areaY: number;
  areaSize: number;
}

export interface LabelShape {
  id: string;
  kind: string;
  text: string;
  x: number;
  y: number;
  size: number;
}

export interface CleanSheet {
  walls: WallShape[];
  rooms: RoomShape[];
  labels: LabelShape[];
}

export interface ScaleBar {
  x: number;
  y: number;
  length: number;
  label: string;
  size: number;
}

/** Below this many walls the redraw has no plan shape: show a note instead (D-013). */
export const MIN_WALLS = 3;

const AREA_LINE = 1; // area baseline sits one name-height below the name
const AREA_SIZE = 0.75; // area text relative to the name
const SCALE_BAR_MAX = 0.2; // a scale bar is at most a fifth of the page width
const BAR_LENGTHS_M = [50, 20, 10, 5, 2, 1, 0.5, 0.2, 0.1];

/** SVG `points` from a `[[x, y], …]` polygon, or null if it is not at least a triangle. */
export function polygonPoints(raw: unknown): string | null {
  if (!Array.isArray(raw) || raw.length < 3) return null;
  const pairs: string[] = [];
  for (const point of raw) {
    if (!Array.isArray(point) || point.length !== 2) return null;
    const [x, y] = point as unknown[];
    if (!isFiniteNumber(x) || !isFiniteNumber(y)) return null;
    pairs.push(`${x},${y}`);
  }
  return pairs.join(" ");
}

export function formatArea(m2: number): string {
  return `${m2.toFixed(1)} m²`;
}

/** Map extracted elements to the shapes of the clean view. */
export function buildCleanSheet(elements: RedrawElement[]): CleanSheet {
  const sheet: CleanSheet = { walls: [], rooms: [], labels: [] };
  const printedAreas = elements
    .filter((e) => e.kind === "area" && hasArea(e.bbox))
    .map((e) => center(e.bbox as BBox));

  for (const e of elements) {
    if (!hasArea(e.bbox)) continue;
    const [x0, y0, x1, y1] = e.bbox;
    if (e.kind === "wall") {
      sheet.walls.push({ id: e.id, x: x0, y: y0, width: x1 - x0, height: y1 - y0 });
      continue;
    }
    const text = (e.label ?? e.text ?? "").trim();
    if (!text) continue;
    const [cx, cy] = center(e.bbox);
    const size = y1 - y0;
    if (e.kind === "room") {
      sheet.rooms.push({
        id: e.id,
        points: polygonPoints(e.properties.polygon_px),
        name: text,
        title: e.name ?? text,
        area: roomArea(e, printedAreas),
        x: cx,
        y: cy,
        size,
        areaY: cy + AREA_LINE * size,
        areaSize: AREA_SIZE * size,
      });
      continue;
    }
    sheet.labels.push({ id: e.id, kind: e.kind, text, x: cx, y: cy, size });
  }
  return sheet;
}

/** Whether the redraw shows enough of the plan to be worth looking at. */
export function hasEnoughForClean(sheet: CleanSheet): boolean {
  return sheet.walls.length >= MIN_WALLS;
}

/**
 * A round-length scale bar for the top-left margin (title blocks sit along the bottom),
 * or null when the scale is unknown.
 */
export function scaleBar(page: Size, mmPerPx: number | null): ScaleBar | null {
  if (!mmPerPx || mmPerPx <= 0) return null;
  const max = page.width * SCALE_BAR_MAX;
  const metres = BAR_LENGTHS_M.find((m) => (m * 1000) / mmPerPx <= max);
  if (metres === undefined) return null;
  const size = page.width / 100;
  const margin = 2 * size;
  return {
    x: margin,
    y: margin,
    length: (metres * 1000) / mmPerPx,
    label: metres >= 1 ? `${metres} m` : `${Math.round(metres * 100)} cm`,
    size,
  };
}

function roomArea(room: RedrawElement, printedAreas: [number, number][]): string | null {
  const m2 = room.properties.area_m2;
  if (!isFiniteNumber(m2)) return null;
  const outline = polygonPoints(room.properties.polygon_px)
    ? (room.properties.polygon_px as [number, number][])
    : null;
  if (outline && printedAreas.some(([x, y]) => insidePolygon(outline, x, y))) return null;
  return formatArea(m2);
}

/** Ray casting: count edge crossings of a horizontal ray from (x, y) to the right. */
function insidePolygon(poly: [number, number][], x: number, y: number): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function center(b: BBox): [number, number] {
  return [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
}

function hasArea(b: BBox | null): b is BBox {
  return b !== null && b[2] > b[0] && b[3] > b[1];
}

function isFiniteNumber(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}
