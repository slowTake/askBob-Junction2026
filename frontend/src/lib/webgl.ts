/** Messages for a 3D viewer that cannot start. Raw errors never reach the page. */

export const NO_WEBGL = "This browser can't show 3D: WebGL is off or unavailable.";
export const VIEWER_FAILED = "The 3D viewer failed to start.";

/** Thrown when the browser can't create a WebGL context. */
export class WebGLUnavailable extends Error {
  constructor() {
    super("WebGL unavailable");
    this.name = "WebGLUnavailable";
  }
}

export function viewerErrorMessage(error: unknown): string {
  return error instanceof WebGLUnavailable ? NO_WEBGL : VIEWER_FAILED;
}
