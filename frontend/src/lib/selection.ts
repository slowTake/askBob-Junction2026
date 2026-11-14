/** Elements selected on the plan: a click selects one, Shift+click adds or removes one. */

import type { ElementInfo } from "../api/types";
import { describe } from "./planLayer";

/**
 * The selection after a click on `el` (null: the empty plan). `additive` is Shift.
 * A plain click selects only `el`, or deselects it when it was the only one selected;
 * Shift+click toggles `el` in the selection and leaves the rest as it is.
 */
export function selectElement<T extends { id: string }>(
  current: readonly T[],
  el: T | null,
  additive: boolean,
): T[] {
  if (el === null) return additive ? [...current] : [];
  const has = current.some((s) => s.id === el.id);
  if (additive) return has ? current.filter((s) => s.id !== el.id) : [...current, el];
  return has && current.length === 1 ? [] : [el];
}

/** What a question is about, shown above it: "room Kitchen", or "3 elements: Kitchen, WC, D1". */
export function aboutLabel(elements: readonly ElementInfo[]): string | null {
  if (elements.length === 0) return null;
  if (elements.length === 1) {
    const [only] = elements;
    return `${only.kind.replaceAll("_", " ")} ${describe(only).title}`;
  }
  return `${elements.length} elements: ${elements.map((e) => describe(e).title).join(", ")}`;
}
