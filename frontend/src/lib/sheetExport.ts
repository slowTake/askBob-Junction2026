/**
 * The redrawn sheet as a file of its own (#82): "Download SVG" and "Print" take the svg
 * drawn on screen and put light-coloured styles inside it, so it opens the same in any
 * viewer and prints without the app around it. Line widths are shares of the page, like
 * the server's render the model checked (app/upscale/sketch_render.py).
 */

import type { Size } from "./camera";

const LINE_SHARE = 0.002;
const SVG_NS = "http://www.w3.org/2000/svg";

/** The redraw's stylesheet with fixed values: no app variables, light paper. */
export function exportCss(page: Size): string {
  const line = LINE_SHARE * Math.max(page.width, page.height);
  const px = (v: number) => `${Math.round(v * 100) / 100}px`;
  return [
    ".clean-bg { fill: #ffffff; }",
    ".clean-room { fill: #f6f8fb; stroke: #c6c6c6; stroke-width: " + px(line / 2) + "; }",
    ".clean-wall, .sketch-wall { fill: #161616; stroke: #161616; stroke-width: " +
      px(line / 4) +
      "; }",
    ".clean-door, .clean-window { fill: #ffffff; stroke: #161616; stroke-width: " +
      px(line) +
      "; }",
    ".clean-window { fill: #f6f8fb; }",
    ".clean-leaf, .clean-gap { fill: none; stroke: #161616; stroke-width: " + px(line) + "; }",
    ".clean-arc { fill: none; stroke: #161616; stroke-width: " + px(line / 2) + "; }",
    ".clean-fixture { fill: none; stroke: #161616; stroke-width: " + px(line / 2) + "; }",
    ".clean-sheet .is-added { stroke: #8a3ffc; }",
    ".clean-wall.is-added { fill: none; }",
    ".sketch-leaf { fill: none; stroke: #161616; stroke-width: " + px(line) + "; }",
    ".sketch-arc, .sketch-window { fill: none; stroke: #161616; stroke-width: " +
      px(line / 2) +
      "; }",
    ".clean-text { fill: #393939; font-family: Helvetica, Arial, sans-serif;" +
      " text-anchor: middle; dominant-baseline: central; }",
    ".clean-room-name { fill: #161616; font-weight: 600; }",
    ".clean-scale path { stroke: #161616; fill: none; }",
    ".clean-scale text { fill: #393939; font-family: Helvetica, Arial, sans-serif; }",
  ].join("\n");
}

/** A complete SVG file from the on-screen svg's markup (XMLSerializer output). */
export function standaloneSvg(markup: string, page: Size): string {
  const start = markup.indexOf("<svg");
  const end = markup.indexOf(">", start);
  if (start !== 0 || end < 0) throw new Error("not an svg element");
  let tag = markup.slice(0, end).replace(/\saria-hidden="[^"]*"/, "");
  if (!/\sxmlns="/.test(tag)) tag += ` xmlns="${SVG_NS}"`;
  const style = `<style><![CDATA[\n${exportCss(page)}\n]]></style>`;
  return `<?xml version="1.0" encoding="UTF-8"?>\n${tag}>${style}${markup.slice(end + 1)}`;
}

/** "napkin.webp", page 0 -> "napkin-page-1-redrawn.svg". */
export function exportFilename(filename: string, pageIndex: number): string {
  const stem =
    filename
      .replace(/\.[^.]*$/, "")
      .replace(/[^\p{L}\p{N}]+/gu, "-")
      .replace(/^-+|-+$/g, "") || "drawing";
  return `${stem}-page-${pageIndex + 1}-redrawn.svg`;
}
