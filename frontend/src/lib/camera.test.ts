import { describe, expect, it } from "vitest";
import {
  clampPan,
  fitContent,
  fitPage,
  fitScale,
  frameBox,
  limits,
  resize,
  zoomAt,
  zoomPercent,
  type BBox,
} from "./camera";

describe("fitScale", () => {
  it("fits the whole page inside the padded viewport", () => {
    // inner area 548 - 2*24 = 500 square; min(500/1000, 500/2000) = 0.25
    expect(fitScale({ width: 1000, height: 2000 }, { width: 548, height: 548 })).toBe(0.25);
  });
});

describe("fitPage", () => {
  it("centres the page", () => {
    // shown 250 x 500; x = 274 - 500*0.25 = 149, y = 274 - 1000*0.25 = 24
    expect(fitPage({ width: 1000, height: 2000 }, { width: 548, height: 548 })).toEqual({
      scale: 0.25,
      x: 149,
      y: 24,
    });
  });
});

describe("frameBox", () => {
  const page = { width: 3000, height: 2000 };
  const viewport = { width: 1048, height: 648 }; // inner 1000 x 600

  it("shows a small target with its surroundings, not as a lone blob", () => {
    const window: BBox = [1000, 500, 1030, 510]; // 30 x 10 px
    // context 0.2 * min(3000, 2000) = 400 px square: min(1000/400, 600/400) = 1.5
    // centre (1015, 505): x = 524 - 1015*1.5 = -998.5, y = 324 - 505*1.5 = -433.5
    expect(frameBox(window, page, viewport)).toEqual({ scale: 1.5, x: -998.5, y: -433.5 });
  });

  it("zooms out to show targets spread over the whole page", () => {
    // min(1000/3000, 600/2000) = 0.3, the same as fitting the page
    expect(frameBox([0, 0, 3000, 2000], page, viewport)).toEqual(fitPage(page, viewport));
  });

  it("never zooms in past the page image's useful resolution", () => {
    const square = { width: 1000, height: 1000 };
    // a 1 px target with no context would need 600x; the cap is 4 screen px per page px
    expect(frameBox([500, 500, 501, 501], square, viewport, 0.001).scale).toBe(4);
  });
});

describe("fitContent", () => {
  const page = { width: 3000, height: 2000 };
  const viewport = { width: 1048, height: 648 }; // inner 1000 x 600

  it("frames the drawing instead of the whole sheet", () => {
    // content 2000 x 1200: min(1000/2000, 600/1200) = 0.5 (the page alone would be 0.3)
    // centre (1500, 1000): x = 524 - 1500*0.5 = -226, y = 324 - 1000*0.5 = -176
    expect(fitContent([500, 400, 2500, 1600], page, viewport)).toEqual({
      scale: 0.5,
      x: -226,
      y: -176,
    });
  });

  it("fits the whole page when there is no content", () => {
    expect(fitContent(null, page, viewport)).toEqual(fitPage(page, viewport));
  });
});

describe("zoomAt", () => {
  it("keeps the page point under the cursor where it is", () => {
    // before: page (100, 50) is under (100, 50); after: (100 - -100)/2 = 100, (50 - -50)/2 = 50
    const lim = { min: 0.1, max: 10 };
    expect(zoomAt({ scale: 1, x: 0, y: 0 }, 2, { x: 100, y: 50 }, lim)).toEqual({
      scale: 2,
      x: -100,
      y: -50,
    });
  });

  it("stops at the zoom limits", () => {
    const cam = { scale: 2, x: 5, y: 7 };
    expect(zoomAt(cam, 2, { x: 100, y: 50 }, { min: 0.5, max: 2 })).toEqual(cam);
  });
});

describe("limits", () => {
  it("allows zooming out to a quarter of the whole page", () => {
    // fit = min(500/1000, 500/1000) = 0.5; min = 0.5 / 4
    expect(limits({ width: 1000, height: 1000 }, { width: 548, height: 548 })).toEqual({
      min: 0.125,
      max: 4,
    });
  });

  it("is relative to Fit when Fit frames only the drawing", () => {
    // Fit scale 0.8 (the drawing is smaller than the sheet): min = 0.8 / 4 = 0.2
    expect(limits({ width: 1000, height: 1000 }, { width: 548, height: 548 }, 0.8)).toEqual({
      min: 0.2,
      max: 4,
    });
  });
});

describe("zoomPercent", () => {
  it("is 100 % at the Fit scale", () => {
    // Fit at 0.25: 0.125 / 0.25 = 50 %, 0.25 / 0.25 = 100 %
    expect(zoomPercent({ scale: 0.125, x: 0, y: 0 }, 0.25)).toBe(50);
    expect(zoomPercent({ scale: 0.25, x: 0, y: 0 }, 0.25)).toBe(100);
  });
});

describe("clampPan", () => {
  it("keeps part of the page in view", () => {
    // 1000 px page at scale 1 in a 500 px viewport, keep 80 px: x in [80-1000, 500-80]
    const page = { width: 1000, height: 1000 };
    const viewport = { width: 500, height: 500 };
    expect(clampPan({ scale: 1, x: 600, y: -2000 }, page, viewport)).toEqual({
      scale: 1,
      x: 420,
      y: -920,
    });
  });
});

describe("resize", () => {
  it("keeps the centre of the view when the viewport changes size", () => {
    // +200 wide moves the page right by 100; -100 high moves it up by 50
    const from = { width: 500, height: 500 };
    const to = { width: 700, height: 400 };
    expect(resize({ scale: 1, x: 10, y: 20 }, from, to)).toEqual({ scale: 1, x: 110, y: -30 });
  });
});
