import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import type { Citation, PlanView } from "../api/types";
import type { Turn } from "../hooks/useAsk";
import { AnswerCard } from "./AnswerCard";

it("presents a cited apartment table once, without repeated controls or confidence badges", () => {
  const view: PlanView = {
    document_id: "d",
    page_id: "p",
    page_index: 0,
    element_ids: ["a", "b"],
    caption: "Apartments A–B",
    line: null,
  };
  const turn: Turn = {
    id: "t",
    question: "List apartment areas",
    about: null,
    steps: [],
    pending: false,
    views: Array(7).fill(view),
    answer: {
      answer: "Two apartments.",
      value: null,
      unit: null,
      confidence: "high",
      verified: true,
      caveats: "Areas exclude balconies.",
      cached: false,
      citations: ["a", "b"].map((element_id) => ({ element_id }) as Citation),
      table: {
        columns: ["Apartment", "Area (m²)"],
        rows: [
          { cells: ["A", "86.26"], citation: 1 },
          { cells: ["B", "81.66"], citation: 2 },
        ],
      },
    },
  };
  const html = renderToStaticMarkup(
    <AnswerCard turn={turn} latest onCitation={() => {}} onShowView={() => {}} />,
  );
  expect(html).toContain("86.26");
  expect(html).toContain("Areas exclude balconies.");
  expect(html).not.toContain("Verified sources");
  expect(html).not.toContain("confidence");
  expect(html).not.toContain("On the plan");
  expect(html).not.toContain("answer-sources");
});
