import type { AnswerTable, Citation, PlanView } from "../api/types";

/** Keep only actions that aren't already available through a table row. */
export function answerActions(
  table: AnswerTable | undefined,
  citations: Citation[],
  views: PlanView[],
): { sources: { citation: Citation; index: number }[]; views: PlanView[] } {
  const referenced = new Set(table?.rows.map((row) => row.citation - 1) ?? []);
  const covered = new Set(
    citations
      .filter((_, i) => referenced.has(i))
      .map((c) => c.element_id)
      .filter(Boolean),
  );
  const seen = new Set<string>();
  const remainingViews = views.filter((view) => {
    if (!view.line && view.element_ids.length && view.element_ids.every((id) => covered.has(id))) {
      return false;
    }
    // Captions can change between agent rounds; the actual drawing action is the identity.
    const key = JSON.stringify([
      view.document_id,
      view.page_id,
      view.page_index,
      [...new Set(view.element_ids)].sort(),
      view.line,
    ]);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  return {
    sources: citations
      .map((citation, index) => ({ citation, index }))
      .filter((s) => !referenced.has(s.index)),
    views: remainingViews,
  };
}
