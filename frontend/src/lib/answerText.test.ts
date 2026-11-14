import { describe, expect, it } from "vitest";
import { answerBlocks } from "./answerText";

describe("answerBlocks", () => {
  it("keeps a plain answer as one paragraph", () => {
    expect(answerBlocks("The kitchen is 12.5 m².")).toEqual([
      { type: "p", text: "The kitchen is 12.5 m²." },
    ]);
  });

  it("splits a summary, group headings and their items", () => {
    const text = [
      "About 20 doors and 14 windows.",
      "",
      "Lower floor:",
      "- 11 windows on the outer walls",
      "- 11 swing doors",
      "Upper floor:",
      "- 6 swing doors",
      "- 3 windows",
    ].join("\n");
    expect(answerBlocks(text)).toEqual([
      { type: "p", text: "About 20 doors and 14 windows." },
      { type: "heading", text: "Lower floor" },
      { type: "list", items: ["11 windows on the outer walls", "11 swing doors"] },
      { type: "heading", text: "Upper floor" },
      { type: "list", items: ["6 swing doors", "3 windows"] },
    ]);
  });

  it("accepts • and * bullets and drops bold markers", () => {
    expect(answerBlocks("Two rooms:\n• **Kitchen** 12 m²\n* WC 2 m²")).toEqual([
      { type: "heading", text: "Two rooms" },
      { type: "list", items: ["Kitchen 12 m²", "WC 2 m²"] },
    ]);
  });

  it("joins wrapped lines of a paragraph and separates paragraphs at blank lines", () => {
    expect(answerBlocks("First line\nwraps here.\n\nSecond paragraph.")).toEqual([
      { type: "p", text: "First line wraps here." },
      { type: "p", text: "Second paragraph." },
    ]);
  });

  it("treats only a short line ending in a colon as a heading", () => {
    // A long sentence that happens to end with ":" stays a paragraph.
    const long = `${"word ".repeat(15).trim()}:`;
    expect(answerBlocks(long)).toEqual([{ type: "p", text: long }]);
  });

  it("is empty for an empty answer", () => {
    expect(answerBlocks("  \n ")).toEqual([]);
  });
});
