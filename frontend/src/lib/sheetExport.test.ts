import { describe, expect, it } from "vitest";
import { exportCss, exportFilename, standaloneSvg } from "./sheetExport";

const PAGE = { width: 2000, height: 1000 };

describe("exportCss", () => {
  it("uses fixed light colours and no app variables, so the file stands alone", () => {
    const css = exportCss(PAGE);
    expect(css).not.toContain("var(");
    expect(css).toContain("#ffffff"); // paper
    expect(css).toContain("#161616"); // walls and symbols
  });

  it("sizes lines to the page, as the server render does", () => {
    // 0.2 % of the longer side, 2000 px: 4 px; door arcs and window lines half that.
    expect(exportCss(PAGE)).toContain("stroke-width: 4px");
    expect(exportCss(PAGE)).toContain("stroke-width: 2px");
  });
});

describe("standaloneSvg", () => {
  const onScreen =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2000 1000" width="2000" height="1000" class="clean-sheet" aria-hidden="true"><rect class="clean-bg"/></svg>';

  it("puts the styles inside the svg, right after its opening tag", () => {
    const file = standaloneSvg(onScreen, PAGE);
    expect(file.startsWith('<?xml version="1.0" encoding="UTF-8"?>\n<svg ')).toBe(true);
    const open = file.indexOf(">", file.indexOf("<svg")) + 1;
    expect(file.slice(open)).toMatch(/^<style><!\[CDATA\[/);
    expect(file).toContain('<rect class="clean-bg"/></svg>');
  });

  it("drops the screen-only attributes and adds the namespace when missing", () => {
    const file = standaloneSvg('<svg class="clean-sheet" aria-hidden="true"><g/></svg>', PAGE);
    expect(file).toContain('xmlns="http://www.w3.org/2000/svg"');
    expect(file).not.toContain("aria-hidden");
    expect(file).toContain('class="clean-sheet"'); // the styles select on it
  });

  it("refuses markup that is not an svg", () => {
    expect(() => standaloneSvg("<div></div>", PAGE)).toThrow();
  });
});

describe("exportFilename", () => {
  it("names the file after the drawing and page", () => {
    expect(exportFilename("napkin.webp", 0)).toBe("napkin-page-1-redrawn.svg");
    expect(exportFilename("Plan A (v2).png", 2)).toBe("Plan-A-v2-page-3-redrawn.svg");
    expect(exportFilename("", 0)).toBe("drawing-page-1-redrawn.svg");
  });
});
