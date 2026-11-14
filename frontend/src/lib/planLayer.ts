/** Pure helpers for the interactive plan layer: which elements show, their shape, their text. */

import type { ElementInfo } from "../api/types";
import type { BBox } from "./viewport";

export type LayerKey = "rooms" | "openings" | "fixtures" | "walls" | "labels";

export const LAYERS: { key: LayerKey; label: string; kinds: string[] }[] = [
  { key: "rooms", label: "Rooms", kinds: ["room", "unit"] },
  { key: "openings", label: "Doors & windows", kinds: ["door", "window"] },
  { key: "fixtures", label: "Fixtures", kinds: ["fixture", "stair", "column"] },
  { key: "walls", label: "Walls", kinds: ["wall"] },
  { key: "labels", label: "Text", kinds: ["text", "dimension", "area", "room_number", "scale"] },
];

export function layerOf(kind: string): LayerKey | null {
  return LAYERS.find((l) => l.kinds.includes(kind))?.key ?? null;
}

export type Shape =
  | { type: "polygon"; points: string }
  | { type: "rect"; x: number; y: number; width: number; height: number };

/** The room outline when we have it, otherwise the element's box. */
export function shapeOf(el: ElementInfo): Shape | null {
  const polygon = el.properties.polygon_px;
  if (Array.isArray(polygon) && polygon.length >= 3) {
    const points = (polygon as number[][]).map(([x, y]) => `${x},${y}`).join(" ");
    return { type: "polygon", points };
  }
  if (!el.bbox) return null;
  const [x0, y0, x1, y1] = el.bbox;
  return { type: "rect", x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
}

/** Drawing order: big areas first, so doors and fixtures inside rooms stay clickable. */
export function drawOrder(elements: ElementInfo[]): ElementInfo[] {
  const rank = (el: ElementInfo) => (el.kind === "unit" ? 0 : el.kind === "room" ? 1 : 2);
  return [...elements].sort((a, b) => rank(a) - rank(b));
}

/** Title and detail lines for the info card, e.g. "Kitchen" / "No. B103 · 13.0 m²". */
export function describe(el: ElementInfo): { title: string; details: string[] } {
  const p = el.properties;
  const title = el.text ?? el.name ?? el.label ?? el.kind;
  const details: string[] = [];
  if (el.name && el.name !== title) details.push(el.name);
  if (typeof p.number === "string") details.push(`No. ${p.number}`);
  if (typeof p.area_m2 === "number") details.push(`${p.area_m2.toFixed(2)} m²`);
  if (typeof p.unit === "string") details.push(`Apartment ${p.unit}`);
  if (el.value_mm && (el.kind === "door" || el.kind === "window")) {
    details.push(`${Math.round(el.value_mm)} mm wide`);
  }
  if (typeof p.subtype === "string") details.push(p.subtype);
  details.push(
    el.confidence < 1 ? `${el.source}, ${Math.round(el.confidence * 100)}% sure` : el.source,
  );
  return { title, details };
}

/** The box around the given elements (to scroll them into view), or null if none has a box. */
export function unionBox(elements: ElementInfo[], ids: Set<string>): BBox | null {
  const boxes = elements.filter((e) => ids.has(e.id) && e.bbox).map((e) => e.bbox as BBox);
  if (boxes.length === 0) return null;
  return [
    Math.min(...boxes.map((b) => b[0])),
    Math.min(...boxes.map((b) => b[1])),
    Math.max(...boxes.map((b) => b[2])),
    Math.max(...boxes.map((b) => b[3])),
  ];
}
