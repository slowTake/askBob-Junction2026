"""Exact geometry from a PDF's vector layer.

Hatched walls in CAD-exported PDFs are drawn as a clip path (the wall outline)
followed by tiles of a pattern. PyMuPDF reports pattern tiles in pattern space,
outside the page, which is what tells a hatched region from any other clip.
"""

from typing import Any

import pymupdf

from app.domain.geometry import Point, polygon_area
from app.domain.polygons import path_polygon

MIN_WALL_PT2 = 4.0  # ignore slivers under 2 x 2 pt
MAX_PAGE_FRACTION = 0.5  # a clip covering half the page is a frame, not a wall


def hatched_regions(page: pymupdf.Page) -> list[list[Point]]:
    """Outlines of pattern-filled regions, in rendered-page point coordinates."""
    drawings = page.get_drawings(extended=True)
    page_area = page.rect.width * page.rect.height
    out: list[list[Point]] = []
    for i, d in enumerate(drawings[:-1]):
        if d["type"] != "clip":
            continue
        nxt = drawings[i + 1]
        if nxt["type"] not in ("f", "fs") or nxt["rect"].intersects(page.mediabox):
            continue  # not followed by pattern content
        polygon = _polygon(d["items"], page)
        area = polygon_area(polygon)
        if MIN_WALL_PT2 <= area <= MAX_PAGE_FRACTION * page_area:
            out.append(polygon)
    return out


def _polygon(items: list[Any], page: pymupdf.Page) -> list[Point]:
    """PyMuPDF path items -> polygon, mapped like the rendered pixmap (rotation applied)."""
    matrix = page.rotation_matrix
    ops: list[tuple[str, list[Point]]] = []
    for item in items:
        op = item[0]
        if op == "re":
            rect = pymupdf.Rect(item[1]) * matrix
            ops.append(("re", [(rect.x0, rect.y0), (rect.x1, rect.y1)]))
        elif op == "qu":
            quad = item[1]
            pts = [pymupdf.Point(p) * matrix for p in (quad.ul, quad.ur, quad.lr, quad.ll)]
            ops.append(("l", [(p.x, p.y) for p in pts]))
        else:
            pts = [pymupdf.Point(p) * matrix for p in item[1:] if hasattr(p, "x")]
            ops.append((op, [(p.x, p.y) for p in pts]))
    return path_polygon(ops)
