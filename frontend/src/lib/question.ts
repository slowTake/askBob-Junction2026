/** What a question is about. A conversation belongs to one document, so its questions are
 * about that document even when an answer has opened another one on the plan: the page
 * on screen and the selected elements only count when they belong to it (PR #92 review). */

import type { AskContext } from "../api/types";

interface Args {
  chatDocId: string; // the document whose conversation is on screen
  openDocId: string | null; // the document open on the plan
  pageOnScreen: number | null; // page index on the plan, null when no plan page is shown
  about: readonly { id: string; document_id: string }[]; // selected to ask about
  onlyThisDocument: boolean; // the scope toggle under the question box
}

export function questionContext(args: Args): { documentIds: string[]; context: AskContext } {
  const { chatDocId, openDocId, pageOnScreen, about, onlyThisDocument } = args;
  const open = openDocId === chatDocId;
  return {
    documentIds: onlyThisDocument ? [chatDocId] : [],
    context: {
      document_id: chatDocId,
      page_index: open ? pageOnScreen : null,
      element_id: null,
      element_ids: open ? about.filter((e) => e.document_id === chatDocId).map((e) => e.id) : [],
    },
  };
}
