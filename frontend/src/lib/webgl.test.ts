import { describe, expect, it } from "vitest";
import { NO_WEBGL, VIEWER_FAILED, viewerErrorMessage, WebGLUnavailable } from "./webgl";

describe("viewerErrorMessage", () => {
  it("explains a browser without WebGL (#73)", () => {
    expect(viewerErrorMessage(new WebGLUnavailable())).toBe(NO_WEBGL);
  });

  it("gives a generic message for anything else, never the raw error", () => {
    expect(viewerErrorMessage(new Error("Cannot read properties of undefined"))).toBe(
      VIEWER_FAILED,
    );
    expect(viewerErrorMessage("boom")).toBe(VIEWER_FAILED);
  });
});
