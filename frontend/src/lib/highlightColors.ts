import type { ElementInfo } from "../api/types";

type HighlightElement = Pick<ElementInfo, "id" | "kind" | "label" | "properties">;

const PALETTE = [
  "#2563eb",
  "#c2410c",
  "#15803d",
  "#9333ea",
  "#be123c",
  "#0e7490",
  "#a16207",
  "#4338ca",
  "#047857",
  "#a21caf",
];

/** Apartments are individual groups; rooms share a category; other objects share a kind. */
function groupOf(el: HighlightElement): string {
  const detail =
    el.kind === "unit"
      ? el.properties.unit || el.label || el.id
      : el.kind === "room"
        ? el.properties.category
        : null;
  return `${el.kind}:${typeof detail === "string" ? detail.trim().toLowerCase() : ""}`;
}

/** Use the whole page so changing the highlighted subset never changes its colors. */
export function highlightColors(
  elements: readonly HighlightElement[],
): ReadonlyMap<string, string> {
  const groups = [...new Set(elements.map(groupOf))].sort();
  const colors = new Map(
    groups.map((key, i) => [key, PALETTE[i] ?? `hsl(${(i * 137.508) % 360} 65% 38%)`]),
  );
  return new Map(elements.map((el) => [el.id, colors.get(groupOf(el))!]));
}
