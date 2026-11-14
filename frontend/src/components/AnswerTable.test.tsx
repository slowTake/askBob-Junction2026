import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AnswerTable } from "./AnswerTable";
import type { Citation } from "../api/types";

describe("AnswerTable", () => {
  it("shows five rows initially and offers the full inventory without hiding its size", () => {
    const html = renderToStaticMarkup(
      <AnswerTable
        table={{
          columns: ["Window", "Width (mm)"],
          rows: Array.from({ length: 20 }, (_, i) => ({
            cells: [`Window ${i + 1}`, "900"],
            citation: 0,
          })),
        }}
        citations={[]}
        onCitation={() => {}}
      />,
    );
    expect(html).toContain("Show all 20");
    expect(html).toContain("Window 5");
    expect(html).not.toContain("Window 6");
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('scope="col"');
  });

  it("links cited items and renders missing sources, unknown values and HTML safely", () => {
    const html = renderToStaticMarkup(
      <AnswerTable
        table={{
          columns: ["Window", "Width (mm)"],
          rows: [
            { cells: ["W1", "900"], citation: 1 },
            { cells: ["<script>", ""], citation: 2 },
          ],
        }}
        citations={[{ note: "Window" } as Citation]}
        onCitation={() => {}}
      />,
    );
    expect(html.match(/class="answer-item-link"/g)).toHaveLength(1);
    expect(html).toContain("&lt;script&gt;");
    expect(html).toContain("—");
    expect(html).not.toContain("Show all");
  });
});
