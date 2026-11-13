import { describe, expect, it } from "vitest";
import { scrollToCenter } from "./viewport";

const page = { width: 2000, height: 1000 };

describe("scrollToCenter", () => {
  it("centres the box", () => {
    // Shown at 4000 px wide -> scale 2. Box centre (1000, 500) -> (2000, 1000) on screen.
    // Viewport 800x600 -> scroll (2000 - 400, 1000 - 300) = (1600, 700).
    expect(scrollToCenter([900, 400, 1100, 600], page, 4000, { width: 800, height: 600 })).toEqual({
      left: 1600,
      top: 700,
    });
  });

  it("clamps at the page edges", () => {
    // Box near the top-left corner: centre would need negative scroll, so 0.
    expect(scrollToCenter([0, 0, 10, 10], page, 4000, { width: 800, height: 600 })).toEqual({
      left: 0,
      top: 0,
    });
    // Box at the bottom-right: max scroll is (4000 - 800, 2000 - 600) = (3200, 1400).
    expect(
      scrollToCenter([1990, 990, 2000, 1000], page, 4000, { width: 800, height: 600 }),
    ).toEqual({ left: 3200, top: 1400 });
  });
});
