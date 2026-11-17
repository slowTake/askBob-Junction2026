import { describe, expect, it } from "vitest";
import { assetPath, findRecording, normalizeQuestion, type Recording } from "./snapshot";

const rec = (question: string, document_ids: string[]): Recording => ({
  question,
  document_ids,
  events: [],
});

describe("normalizeQuestion", () => {
  it("ignores case, extra spaces and closing punctuation", () => {
    // By the rule: lower case, runs of whitespace become one space, trailing ?!. dropped.
    expect(normalizeQuestion("  How many  ROOMS are there?! ")).toBe("how many rooms are there");
  });

  it("keeps punctuation inside the question", () => {
    expect(normalizeQuestion("Show them. All of them.")).toBe("show them. all of them");
  });
});

describe("findRecording", () => {
  const a = rec("How many rooms?", ["doc-a"]);
  const b = rec("How many rooms?", ["doc-b"]);
  const both = rec("How many rooms?", ["doc-a", "doc-b"]);

  it("finds nothing for a question that was never recorded", () => {
    expect(findRecording([a, b], "Where is the sauna?", ["doc-a"], null)).toBeNull();
  });

  it("prefers the recording asked about the same documents, in any order", () => {
    expect(findRecording([a, b, both], "how many rooms", ["doc-b", "doc-a"], null)).toBe(both);
    expect(findRecording([a, b, both], "how many rooms", ["doc-b"], null)).toBe(b);
  });

  it("falls back to a recording about the document on screen", () => {
    // Asked about every document, recorded per document: the one being looked at wins.
    expect(findRecording([a, b], "How many rooms?", ["doc-a", "doc-b", "doc-c"], "doc-b")).toBe(b);
  });

  it("falls back to the first recording of the question", () => {
    expect(findRecording([a, b], "How many rooms?", ["doc-c"], null)).toBe(a);
  });
});

describe("assetPath", () => {
  it("names each recorded file under its document", () => {
    expect(assetPath("d1", { page: 2 })).toBe("documents/d1/page-2.png");
    expect(assetPath("d1", { elements: 0 })).toBe("documents/d1/elements-0.json");
    expect(assetPath("d1", { upscale: 1 })).toBe("documents/d1/upscale-1.json");
    expect(assetPath("d1", "mesh")).toBe("documents/d1/mesh.json");
    expect(assetPath("d1", "ifc")).toBe("documents/d1/model.ifc");
  });
});
