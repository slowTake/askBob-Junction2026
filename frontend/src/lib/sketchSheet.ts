/**
 * The redrawn page of a hand-drawn sketch (#82). The backend's model authored the whole
 * plan and stored each element's drawing in page pixels (app/domain/sketch_drawing.py);
 * the model checked a server render of these same shapes. Only those elements are drawn:
 * ingest's OCR and line elements on a sketch are the noise the redraw replaces.
 *
 * Nothing is measured here. There is no scale bar and no area; text is only what was
 * written on the sketch.
 */

import type { UpscaleInfo } from "../api/types";
import type { Size } from "./camera";
import { polygonPoints, scaleBar, type RedrawElement, type ScaleBar } from "./redraw";

/** `Element.source` of the sketch redraw (backend `SKETCH_SOURCE`). */
export const SKETCH_SOURCE = "sketch";

export interface SketchSheet {
  walls: { id: string; pieces: string[]; outer: boolean }[];
  doors: { id: string; leaf: string; arc: string }[];
  windows: { id: string; lines: string[] }[];
  rooms: { id: string; name: string; x: number; y: number; size: number }[];
  texts: { id: string; text: string; x: number; y: number; size: number }[];
}

/** `page.upscale.mode` of a page the sketch redraw ran on (backend `SKETCH_MODE`). */
export const SKETCH_MODE: NonNullable<UpscaleInfo["mode"]> = "sketch";

/** Documents whose pages get the sketch redraw: raster images (backend `is_sketch_page`). */
export function isSketchDocument(kind: string, hasCadRooms = false): boolean {
  return kind === "image" && !hasCadRooms;
}

/** The elements the plan layer offers: on a redrawn sketch, only the model's plan. */
export function planElements<T extends { source: string }>(elements: T[], sketch: boolean): T[] {
  return sketch ? elements.filter((e) => e.source === SKETCH_SOURCE) : elements;
}

/** The redraw's scale bar: none on a sketch, whatever scale ingest guessed for the page. */
export function redrawScaleBar(
  page: Size,
  mmPerPx: number | null,
  sketch: boolean,
): ScaleBar | null {
  return sketch ? null : scaleBar(page, mmPerPx);
}

/** SVG `points` of an open line through at least two numeric points, or null. */
export function polylinePoints(raw: unknown): string | null {
  if (!Array.isArray(raw) || raw.length < 2) return null;
  const pairs: string[] = [];
  for (const point of raw) {
    if (!Array.isArray(point) || point.length !== 2) return null;
    const [x, y] = point as unknown[];
    if (!isFiniteNumber(x) || !isFiniteNumber(y)) return null;
    pairs.push(`${x},${y}`);
  }
  return pairs.join(" ");
}

export function buildSketchSheet(elements: RedrawElement[]): SketchSheet {
  const sheet: SketchSheet = { walls: [], doors: [], windows: [], rooms: [], texts: [] };
  for (const e of elements) {
    if (e.source !== SKETCH_SOURCE) continue;
    const p = e.properties;
    if (e.kind === "wall") {
      const raw = Array.isArray(p.pieces_px) ? p.pieces_px : [];
      const pieces = raw.map(polygonPoints).filter((s): s is string => s !== null);
      if (pieces.length) sheet.walls.push({ id: e.id, pieces, outer: p.thickness === "outer" });
    } else if (e.kind === "door") {
      const leaf = polylinePoints(p.leaf_px);
      const arc = polylinePoints(p.arc_px);
      if (leaf && arc) sheet.doors.push({ id: e.id, leaf, arc });
    } else if (e.kind === "window") {
      const raw = Array.isArray(p.lines_px) ? p.lines_px : [];
      const lines = raw.map(polylinePoints).filter((s): s is string => s !== null);
      if (lines.length) sheet.windows.push({ id: e.id, lines });
    } else if (e.kind === "room" || e.kind === "text") {
      const text = (e.kind === "room" ? (e.name ?? e.text) : e.text)?.trim();
      const at = labelPoint(p.label_px);
      if (!text || !at || !isFiniteNumber(p.font_px)) continue;
      const shape = { id: e.id, x: at[0], y: at[1], size: p.font_px };
      if (e.kind === "room") sheet.rooms.push({ ...shape, name: text });
      else sheet.texts.push({ ...shape, text });
    }
  }
  return sheet;
}

function labelPoint(raw: unknown): [number, number] | null {
  if (!Array.isArray(raw) || raw.length !== 2) return null;
  const [x, y] = raw as unknown[];
  return isFiniteNumber(x) && isFiniteNumber(y) ? [x, y] : null;
}

function isFiniteNumber(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}
