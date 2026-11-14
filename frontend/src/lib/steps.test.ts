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

describe("describeStep for the area and plan tools", () => {
  it("says what the agent is doing, not the tool's name", () => {
    expect(describeStep("sum_room_areas", { unit: "A", name: null })).toBe(
      "Adding up the room areas of apartment A",
    );
    expect(describeStep("sum_room_areas", { unit: null, name: null })).toBe(
      "Adding up the room areas",
    );
    expect(describeStep("highlight", { element_ids: ["a", "b", "c"] })).toBe(
      "Showing 3 elements on the plan",
    );
    expect(describeStep("measure_between", {})).toBe("Measuring between two elements");
  });
});
