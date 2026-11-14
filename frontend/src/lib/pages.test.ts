import { describe, expect, it } from "vitest";
import { pageIndexFor } from "./pages";

describe("pageIndexFor", () => {
  it("starts on the first page when nothing was chosen yet", () => {
    expect(pageIndexFor(null, "doc-a")).toBe(0);
  });

  it("keeps the chosen page for the document it was chosen on", () => {
    expect(pageIndexFor({ documentId: "doc-a", index: 2 }, "doc-a")).toBe(2);
  });

  it("falls back to the first page when another document becomes selected", () => {
    // Page 3 of a three-page PDF, then an upload selects a one-page PDF (#6).
    expect(pageIndexFor({ documentId: "doc-a", index: 2 }, "doc-b")).toBe(0);
  });

  it("falls back to the first page when no document is selected", () => {
    expect(pageIndexFor({ documentId: "doc-a", index: 2 }, null)).toBe(0);
  });
});
