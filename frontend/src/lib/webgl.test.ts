import { describe, expect, it } from "vitest";
import { viewerErrorMessage, WebGLUnavailable } from "./webgl";

describe("viewerErrorMessage", () => {
  it("explains a browser without WebGL (#73)", () => {
    expect(viewerErrorMessage(new WebGLUnavailable())).toBe(
      "This browser can't show 3D: WebGL is off or unavailable.",
    );
  });

  it("gives a generic message for anything else, never the raw error", () => {
    const failed = "The 3D viewer failed to start.";
    expect(viewerErrorMessage(new Error("Cannot read properties of undefined"))).toBe(failed);
    expect(viewerErrorMessage("boom")).toBe(failed);
  });
});
