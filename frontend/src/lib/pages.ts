/** Which page of the selected document to show. */

export interface PageRef {
  documentId: string;
  index: number;
}

/**
 * The page the user chose, but only while the document it was chosen on is still the
 * selected one. Any other way of changing the selection (upload, delete, a citation in
 * another document) starts on the first page, so a stale index can never point past
 * the end of a shorter document.
 */
export function pageIndexFor(chosen: PageRef | null, selectedId: string | null): number {
  return chosen !== null && chosen.documentId === selectedId ? chosen.index : 0;
}
