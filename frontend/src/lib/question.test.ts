import { describe, expect, it } from "vitest";
import { questionContext } from "./question";

const e1 = { id: "e1", document_id: "A" };
const e2 = { id: "e2", document_id: "A" };
const eB = { id: "eB", document_id: "B" };

describe("questionContext", () => {
  it("asks about the conversation's document, with its page and selection when it is open", () => {
    expect(
      questionContext({
        chatDocId: "A",
        openDocId: "A",
        pageOnScreen: 2,
        about: [e1, e2],
        onlyThisDocument: true,
      }),
    ).toEqual({
      documentIds: ["A"],
      context: { document_id: "A", page_index: 2, element_id: null, element_ids: ["e1", "e2"] },
    });
  });

  it("stays on the conversation's document when an answer opened another one (review #2)", () => {
    // A's chat is on screen, but the agent opened B: the question is about A, and B's
    // page and B's selected elements are not sent with it.
    expect(
      questionContext({
        chatDocId: "A",
        openDocId: "B",
        pageOnScreen: 0,
        about: [eB],
        onlyThisDocument: true,
      }),
    ).toEqual({
      documentIds: ["A"],
      context: { document_id: "A", page_index: null, element_id: null, element_ids: [] },
    });
  });

  it("searches every document when the scope toggle is off, keeping the context", () => {
    const { documentIds, context } = questionContext({
      chatDocId: "A",
      openDocId: "A",
      pageOnScreen: null, // the 3D tab is open: no page
      about: [],
      onlyThisDocument: false,
    });
    expect(documentIds).toEqual([]);
    expect(context).toEqual({
      document_id: "A",
      page_index: null,
      element_id: null,
      element_ids: [],
    });
  });
});
