/** Which views a document offers: the plan for anything with pages, 3D only for real models. */

export type View = "drawing" | "model";

export function availableViews(doc: { page_count: number; has_model: boolean }): View[] {
  const views: View[] = [];
  if (doc.page_count > 0) views.push("drawing");
  if (doc.has_model) views.push("model");
  return views;
}

/** The requested view if offered, else the first one offered (the plan, when there is one). */
export function pickView(requested: View, available: View[]): View | null {
  return available.includes(requested) ? requested : (available[0] ?? null);
}
