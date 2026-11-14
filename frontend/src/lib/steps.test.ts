import { describe, expect, it } from "vitest";
import { currentStatus, describeStep } from "./steps";

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

describe("describeStep for quantity totals", () => {
  it("names the quantity in plain words, the kind and the storey", () => {
    expect(
      describeStep("sum_quantity", { kind: "wall", quantity: "NetSideArea", storey: "5. Sal" }),
    ).toBe("Adding up the net side area of walls on 5. Sal");
    expect(
      describeStep("sum_quantity", { kind: "slab", quantity: "NetVolume", storey: null }),
    ).toBe("Adding up the net volume of slabs");
  });
});

describe("currentStatus", () => {
  it("is one line: the latest step, or Thinking before the first", () => {
    expect(currentStatus([])).toBe("Thinking");
    const steps = [
      { tool: "find_elements", input: { kind: "room" } },
      { tool: "view_region", input: {} },
    ];
    expect(currentStatus(steps)).toBe("Looking at the drawing"); // the second, latest step
  });
});
