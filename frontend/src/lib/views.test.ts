import { describe, expect, it } from "vitest";
import { availableViews, pickView } from "./views";

describe("views", () => {
  it("drawings get only the plan", () => {
    expect(availableViews({ page_count: 1, has_model: false })).toEqual(["drawing"]);
  });

  it("IFC models get their storey plans and 3D", () => {
    expect(availableViews({ page_count: 4, has_model: true })).toEqual(["drawing", "model"]);
  });

  it("falls back to what is offered", () => {
    expect(pickView("model", ["drawing"])).toBe("drawing");
    expect(pickView("model", ["drawing", "model"])).toBe("model");
    expect(pickView("drawing", [])).toBeNull();
  });
});
