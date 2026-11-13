import { describe, expect, it } from "vitest";
import { describeStep } from "./steps";

describe("describeStep", () => {
  it("describes a filtered search, with pages counted from 1", () => {
    expect(describeStep("find_elements", { kind: "room", text: "MH", page_index: 0 })).toBe(
      "Searching rooms “MH” on page 1",
    );
  });

  it("describes an unfiltered search", () => {
    expect(describeStep("find_elements", { kind: null, text: null })).toBe("Searching elements");
  });

  it("falls back to the tool name", () => {
    expect(describeStep("new_tool", {})).toBe("new_tool");
  });
});
