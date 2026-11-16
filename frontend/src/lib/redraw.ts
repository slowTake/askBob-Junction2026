/**
 * The redrawn plan page (#82, ported from #54): extracted elements become uniform shapes
 * in the page's own pixel coordinates, so anything placed on the original (citations,
 * highlights, the plan layer) lands on the same spot here. Elements the upscale pass
 * added are flagged so the view can draw them apart from what ingest found.
 */

import type { BBox, Size } from "./camera";

/** `Element.source` of what the upscale vision pass added (backend `UPSCALE_SOURCE`). */
export const UPSCALE_SOURCE = "upscale";

/** The fields of an extracted element (`ElementInfo`) the redraw reads. */
export interface RedrawElement {
  id: string;
  kind: string;
  bbox: BBox | null;
  label: string | null;
  name: string | null;
  text: string | null;
  properties: Record<string, unknown>;
  source: string;
  confidence: number;
}

export interface WallShape {
  id: string;
  /** SVG `points`: the wall's outline when ingest kept one, else its box. */
  points: string;
  added: boolean;
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
  added: boolean;
}

export interface OpeningShape {
  id: string;
  kind: "door" | "window";
  /** The box, drawn when ingest stored no gap (`properties.opening`). */
  x: number;
  y: number;
  width: number;
  height: number;
  added: boolean;
  /** SVG path of the gap on its wall: an opening with a stored gap but no swing or frame. */
  gap: string | null;
  /** A door with a stored swing (D-055): its leaf from the hinge, and the arc back to the wall. */
  leaf: string | null;
  arc: string | null;
  /** A window's frame as drawn, SVG `points`. */
  frame: string | null;
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
  openings: OpeningShape[];
  labels: LabelShape[];
}

export interface ScaleBar {
  x: number;
  y: number;
  length: number;
  label: string;
  size: number;
}

// One font size per page, never the OCR box's height: handwriting and misreads make boxes
// of any size, and the redraw is meant to read evenly.
const TEXT_SHARE = 1 / 100; // text size as a share of the page width (as the scale bar)
const ROOM_SIZE = 1.5; // room names relative to other text
const AREA_LINE = 1; // area baseline sits one name-height below the name
const AREA_SIZE = 0.75; // area text relative to the name
const MIN_TEXT_CONFIDENCE = 0.6; // unclassified OCR text below this is mostly noise
const HAS_WORD = /[\p{L}\p{N}]/u;
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

/** Map extracted elements to the shapes of the redrawn view of a page of this size. */
export function buildCleanSheet(elements: RedrawElement[], page: Size): CleanSheet {
  const textSize = page.width * TEXT_SHARE;
  const roomSize = ROOM_SIZE * textSize;
  const sheet: CleanSheet = { walls: [], rooms: [], openings: [], labels: [] };
  const printedAreas = elements
    .filter((e) => e.kind === "area" && hasArea(e.bbox))
    .map((e) => center(e.bbox as BBox));

  for (const e of elements) {
    if (!hasArea(e.bbox)) continue;
    const [x0, y0, x1, y1] = e.bbox;
    const added = e.source === UPSCALE_SOURCE;
    if (e.kind === "wall") {
      const points =
        polygonPoints(e.properties.polygon_px) ?? `${x0},${y0} ${x1},${y0} ${x1},${y1} ${x0},${y1}`;
      sheet.walls.push({ id: e.id, points, added });
      continue;
    }
    if (e.kind === "door" || e.kind === "window") {
      sheet.openings.push({
        id: e.id,
        kind: e.kind,
        x: x0,
        y: y0,
        width: x1 - x0,
        height: y1 - y0,
        added,
        ...storedOpening(e.kind, e.properties),
      });
      continue;
    }
    const text = (e.label ?? e.text ?? "").trim();
    if (!text) continue;
    if (e.kind === "text" && !isLegible(text, e.confidence)) continue;
    const [cx, cy] = center(e.bbox);
    if (e.kind === "room") {
      sheet.rooms.push({
        id: e.id,
        points: polygonPoints(e.properties.polygon_px),
        name: text,
        title: e.name ?? text,
        area: roomArea(e, printedAreas),
        x: cx,
        y: cy,
        size: roomSize,
        areaY: cy + AREA_LINE * roomSize,
        areaSize: AREA_SIZE * roomSize,
        added,
      });
      continue;
    }
    sheet.labels.push({ id: e.id, kind: e.kind, text, x: cx, y: cy, size: textSize });
  }
  return sheet;
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

type Point = [number, number];
type StoredShape = Pick<OpeningShape, "gap" | "leaf" | "arc" | "frame">;

/**
 * An opening's stored shape (D-055; mirrored by the benchmark's `redraw_elements.py`):
 * a door with a gap, a hinge end ("a" or "b") and a point it opens toward is its leaf and
 * arc; a window with a gap and a frame is its frame; any other gap is its line.
 */
function storedOpening(kind: string, properties: Record<string, unknown>): StoredShape {
  const none: StoredShape = { gap: null, leaf: null, arc: null, frame: null };
  const opening = properties.opening as Record<string, unknown> | undefined;
  const a = asPoint(opening?.a);
  const b = asPoint(opening?.b);
  if (!a || !b) return none;
  const toward = asPoint(properties.toward);
  const hinge = properties.hinge === "a" ? a : properties.hinge === "b" ? b : null;
  if (kind === "door" && hinge && toward) {
    const free = hinge === a ? b : a;
    const swing = doorSwing(hinge, free, toward);
    if (swing) return { ...none, ...swing };
  }
  const frame = kind === "window" ? polygonPoints(properties.polygon_px) : null;
  if (frame) return { ...none, frame };
  return { ...none, gap: `M${num(a[0])} ${num(a[1])}L${num(b[0])} ${num(b[1])}` };
}

/** The leaf turned open toward `toward` (as long as the gap), and the arc back to `free`. */
function doorSwing(
  hinge: Point,
  free: Point,
  toward: Point,
): Pick<StoredShape, "leaf" | "arc"> | null {
  const r = Math.hypot(free[0] - hinge[0], free[1] - hinge[1]);
  if (r === 0) return null;
  const [ux, uy] = [(free[0] - hinge[0]) / r, (free[1] - hinge[1]) / r];
  let [nx, ny] = [-uy, ux];
  if (nx * (toward[0] - hinge[0]) + ny * (toward[1] - hinge[1]) < 0) [nx, ny] = [-nx, -ny];
  const leaf: Point = [hinge[0] + r * nx, hinge[1] + r * ny];
  // Sweep 1 turns clockwise on screen (y down): from the leaf to the gap when n × u > 0.
  const sweep = nx * uy - ny * ux > 0 ? 1 : 0;
  const [hx, hy, lx, ly] = [hinge[0], hinge[1], leaf[0], leaf[1]].map(num);
  return {
    leaf: `M${hx} ${hy}L${lx} ${ly}`,
    arc: `M${lx} ${ly}A${num(r)} ${num(r)} 0 0 ${sweep} ${num(free[0])} ${num(free[1])}`,
  };
}

function asPoint(raw: unknown): Point | null {
  if (!Array.isArray(raw) || raw.length !== 2) return null;
  const [x, y] = raw as unknown[];
  return isFiniteNumber(x) && isFiniteNumber(y) ? [x, y] : null;
}

/** Two decimals at most, and no "-0". */
function num(v: number): number {
  return Math.round(v * 100) / 100 || 0;
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

/** Free OCR text worth drawing: read with some certainty, and more than punctuation. */
function isLegible(text: string, confidence: number): boolean {
  return confidence >= MIN_TEXT_CONFIDENCE && HAS_WORD.test(text);
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

/** Which base the plan shows: the page image, or the redraw once the page is upscaled. */
export type SheetMode = "original" | "redrawn";
