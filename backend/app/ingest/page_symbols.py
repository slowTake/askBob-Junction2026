"""A raster page's walls with its doors and windows carved out of them (D-055).

The walls are traced once to know where they are; the symbols that lie along them are
found; then the walls are traced again with the symbols' own ink taken off, so a window
frame or a door's arc is drawn as what it is and not as wall. Pure: masks in, elements out.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from app.domain.geometry import BBox, Point, footprint_mm
from app.ingest.rooms import Mask
from app.ingest.symbols import Window, find_windows, window_carve
from app.ingest.types import ExtractedElement
from app.ingest.wall_trace import TracedWall, trace_walls

SYMBOL_CONFIDENCE = 0.5  # read from the drawing's own symbols; vision's are 0.7
WINDOW_SHARE = 0.025  # the shortest window, as a share of the page's longest side: 13 px
MIN_WINDOW_PX = 12


@dataclass(frozen=True)
class PageSymbols:
    walls: list[TracedWall]
    windows: list[Window]


def trace_with_symbols(
    ink: Mask,
    symbols: Mask,
    fills: Mask,
    min_run_px: int,
    text_boxes: Sequence[BBox] = (),
    dimension_boxes: Sequence[BBox] = (),
) -> PageSymbols:
    """The page's walls, traced without the ink of the windows found along them."""
    first = trace_walls(ink, min_run_px, text_boxes, dimension_boxes)
    walls = wall_raster(first, ink.shape)
    min_window = max(MIN_WINDOW_PX, round(WINDOW_SHARE * max(ink.shape)))
    windows = find_windows(symbols, fills, walls, min_window)
    if not windows:
        return PageSymbols(first, [])
    carve = window_carve(windows, ink.shape)
    return PageSymbols(trace_walls(ink, min_run_px, text_boxes, dimension_boxes, carve), windows)


def wall_raster(walls: Sequence[TracedWall], shape: tuple[int, ...]) -> Mask:
    drawn = np.zeros(shape[:2], np.uint8)
    for wall in walls:
        cv2.fillPoly(drawn, [np.round(np.array(wall.polygon)).astype(np.int32)], 1)
    return drawn.astype(bool)


def symbol_elements(
    found: PageSymbols, scale_mm: float | None, page_height: float
) -> list[ExtractedElement]:
    """Doors and windows as stored elements: `properties.opening` holds the gap on its wall."""
    return [_window(w, scale_mm, page_height) for w in found.windows]


def _window(w: Window, scale_mm: float | None, page_height: float) -> ExtractedElement:
    x0, y0, x1, y1 = (float(v) for v in w.box)
    polygon: list[Point] = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    el = ExtractedElement(
        kind="window",
        source="derived",
        bbox=(x0, y0, x1, y1),
        confidence=SYMBOL_CONFIDENCE,
        properties={
            "opening": {"a": list(w.a), "b": list(w.b)},
            "thickness_px": w.thickness_px,
            "polygon_px": [list(p) for p in polygon],
        },
    )
    if scale_mm:
        el.footprint_mm = footprint_mm(polygon, scale_mm, page_height)
        el.value_mm = round(float(np.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1])) * scale_mm, 2)
    return el
