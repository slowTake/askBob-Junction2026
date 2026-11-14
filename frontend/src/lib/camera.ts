/** Pan and zoom for the plan. A camera maps page pixels to viewport pixels:
 * screen = page * scale + (x, y). 100 % zoom means "the whole page fits". */

export type BBox = [number, number, number, number];

export interface Size {
  width: number;
  height: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface Camera {
  scale: number;
  x: number;
  y: number;
}

export interface Limits {
  min: number;
  max: number;
}

export const PADDING_PX = 24;
const MAX_SCALE = 4; // screen px per page px; beyond this the page image only gets blurry
const MIN_OF_FIT = 0.25; // zoom out to a quarter of the whole page
const CONTEXT = 0.2; // a framed target shows at least this share of the page around it
const KEEP_VISIBLE_PX = 80;

/** Scale at which the whole page fits the viewport. */
export function fitScale(page: Size, viewport: Size): number {
  const width = Math.max(viewport.width - 2 * PADDING_PX, 1);
  const height = Math.max(viewport.height - 2 * PADDING_PX, 1);
  return Math.min(width / page.width, height / page.height);
}

export function limits(page: Size, viewport: Size): Limits {
  const fit = fitScale(page, viewport);
  return { min: fit * MIN_OF_FIT, max: Math.max(MAX_SCALE, fit) };
}

/** The whole page, centred. */
export function fitPage(page: Size, viewport: Size): Camera {
  return centreOn([0, 0, page.width, page.height], fitScale(page, viewport), viewport);
}

/**
 * Frame `box` with its surroundings: a small target (one window) is shown with at least
 * `context` of the page around it, so it is never a lone blob; targets spread over the
 * page zoom out until they all fit.
 */
export function frameBox(box: BBox, page: Size, viewport: Size, context = CONTEXT): Camera {
  const side = context * Math.min(page.width, page.height);
  const framed = {
    width: Math.max(box[2] - box[0], side),
    height: Math.max(box[3] - box[1], side),
  };
  const scale = clamp(fitScale(framed, viewport), limits(page, viewport));
  return centreOn(box, scale, viewport);
}

/** Zoom by `factor`, keeping the page point under `at` (viewport px) in place. */
export function zoomAt(camera: Camera, factor: number, at: Point, lim: Limits): Camera {
  const scale = clamp(camera.scale * factor, lim);
  const k = scale / camera.scale;
  if (k === 1) return camera;
  return { scale, x: at.x - (at.x - camera.x) * k, y: at.y - (at.y - camera.y) * k };
}

/** Never pan the page fully out of sight. */
export function clampPan(camera: Camera, page: Size, viewport: Size): Camera {
  const width = page.width * camera.scale;
  const height = page.height * camera.scale;
  return {
    ...camera,
    x: Math.min(Math.max(camera.x, KEEP_VISIBLE_PX - width), viewport.width - KEEP_VISIBLE_PX),
    y: Math.min(Math.max(camera.y, KEEP_VISIBLE_PX - height), viewport.height - KEEP_VISIBLE_PX),
  };
}

/** Zoom label: 100 % when the whole page fits the viewport. */
export function zoomPercent(camera: Camera, page: Size, viewport: Size): number {
  return Math.round((camera.scale / fitScale(page, viewport)) * 100);
}

/** Keep the middle of the view in place when the viewport changes size. */
export function resize(camera: Camera, from: Size, to: Size): Camera {
  return {
    ...camera,
    x: camera.x + (to.width - from.width) / 2,
    y: camera.y + (to.height - from.height) / 2,
  };
}

function centreOn(box: BBox, scale: number, viewport: Size): Camera {
  return {
    scale,
    x: viewport.width / 2 - ((box[0] + box[2]) / 2) * scale,
    y: viewport.height / 2 - ((box[1] + box[3]) / 2) * scale,
  };
}

function clamp(value: number, lim: Limits): number {
  return Math.min(Math.max(value, lim.min), lim.max);
}
