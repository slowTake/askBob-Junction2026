import { describe, expect, it } from "vitest";
import type { Citation, PlanView } from "../api/types";
import { answerActions } from "./answerActions";

const citations = ["a", "b", "c"].map((element_id) => ({ element_id }) as Citation);
const view: PlanView = {
  document_id: "d",
  page_id: "p",
  page_index: 0,
  element_ids: ["a", "b"],
  caption: "Apartments A–B",
  line: null,
};

describe("answerActions", () => {
  it("does not repeat table row sources or a plan action covering the same items", () => {
    const actions = answerActions(
      {
        columns: ["Apartment"],
        rows: [
          { cells: ["A"], citation: 1 },
          { cells: ["B"], citation: 2 },
        ],
      },
      citations,
      [view, view],
    );
    expect(actions.views).toEqual([]);
    expect(actions.sources).toEqual([{ citation: citations[2], index: 2 }]);
  });

  it("deduplicates drawing actions even with different captions and ID order", () => {
    const actions = answerActions(undefined, citations, [
      view,
      {
        ...view,
        caption: "Same apartments",
        element_ids: ["b", "a", "a"],
      },
    ]);
    expect(actions.views).toEqual([view]);
    expect(actions.sources).toHaveLength(3);
  });

  it("keeps distinct pages, additional elements, and measurements accessible", () => {
    const table = { columns: ["Apartment"], rows: [{ cells: ["A"], citation: 1 }] };
    const line = { from: [0, 0] as [number, number], to: [1, 1] as [number, number], label: "1 m" };
    const views = [view, { ...view, page_id: "p2" }, { ...view, element_ids: ["a"], line }];
    expect(answerActions(table, citations, views).views).toEqual(views);
  });

  it("handles absent tables, empty answers and invalid source references", () => {
    expect(answerActions(undefined, [], [])).toEqual({ sources: [], views: [] });
    const actions = answerActions(
      {
        columns: ["Total"],
        rows: [
          { cells: ["20"], citation: 0 },
          { cells: ["Other"], citation: 99 },
        ],
      },
      citations,
      [view],
    );
    expect(actions.sources).toHaveLength(3);
    expect(actions.views).toEqual([view]);
  });

  it("keeps a view that writes a label or draws a route, even over cited rows", () => {
    const labelled = { ...view, labels: [{ at: [1, 2] as [number, number], text: "78.4 m²" }] };
    const routed = {
      ...view,
      element_ids: [],
      path: {
        points: [
          [0, 0],
          [5, 5],
        ] as [number, number][],
        label: "1 m",
      },
    };
    const actions = answerActions(
      {
        columns: ["Apartment"],
        rows: [
          { cells: ["A"], citation: 1 },
          { cells: ["B"], citation: 2 },
        ],
      },
      citations,
      [labelled, routed],
    );
    expect(actions.views).toEqual([labelled, routed]);
  });
});
