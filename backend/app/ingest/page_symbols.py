"""A raster page's walls with its doors and windows carved out of them (D-055).

The walls are traced once to know where they are; the symbols that lie along them are
found; then the walls are traced again with the symbols' own ink taken off, so a window
frame or a door's arc is drawn as what it is and not as wall. The gap a door or window
fills is never cut out of its wall. Pure: masks in, elements out.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from app.domain.geometry import BBox, Point, footprint_mm
from app.ingest.doors import Door, door_carve, find_doors
from app.ingest.rooms import Mask
from app.ingest.symbols import Window, find_windows, window_carve
from app.ingest.types import ExtractedElement
from app.ingest.wall_trace import TracedWall, trace_walls

SYMBOL_CONFIDENCE = 0.5  # read from the drawing's own symbols; vision's are 0.7
WINDOW_SHARE = 0.025  # the shortest window, as a share of the page's longest side: 13 px
MIN_WINDOW_PX = 12
# A door leaf, as a share of the page's longest side: 7..25 px on colorful-34, whose
# doors are 7-23 px wide.
DOOR_SHARES = (0.014, 0.05)
MIN_DOOR_PX = 5


@dataclass(frozen=True)
class PageSymbols:
    walls: list[TracedWall]
    windows: list[Window]
    doors: list[Door]


def trace_with_symbols(
    ink: Mask,
    symbols: Mask,
    fills: Mask,
    min_run_px: int,
    text_boxes: Sequence[BBox] = (),
    dimension_boxes: Sequence[BBox] = (),
) -> PageSymbols:
    """The page's walls, traced without the ink of the doors and windows found on them."""
    first = trace_walls(ink, min_run_px, text_boxes, dimension_boxes)
    walls = wall_raster(first, ink.shape)
    longest = max(ink.shape)
    min_window = max(MIN_WINDOW_PX, round(WINDOW_SHARE * longest))
    windows = find_windows(symbols, fills, walls, min_window)
    smallest, largest = (max(MIN_DOOR_PX, round(s * longest)) for s in DOOR_SHARES)
    doors = find_doors(symbols, ink, walls, smallest, largest)
    if not windows and not doors:
        return PageSymbols(first, [], [])
    # A thin wall line the first trace found stays: a door's leaf or arc that runs along
    # one is drawn on the wall, and the wall is what the truth and the route tool need.
    lines = wall_raster([w for w in first if w.drawn == "line"], ink.shape)
    carve = window_carve(windows, ink.shape) | (door_carve(doors, symbols, ink) & ~lines)
    traced = trace_walls(ink, min_run_px, text_boxes, dimension_boxes, carve)
    return PageSymbols(traced, windows, doors)


def wall_raster(walls: Sequence[TracedWall], shape: tuple[int, ...]) -> Mask:
    drawn = np.zeros(shape[:2], np.uint8)
    for wall in walls:
        cv2.fillPoly(drawn, [np.round(np.array(wall.polygon)).astype(np.int32)], 1)
    return drawn.astype(bool)


def symbol_elements(
    found: PageSymbols, scale_mm: float | None, page_height: float
) -> list[ExtractedElement]:
    """Doors and windows as stored elements: `properties.opening` holds the gap on its
    wall; a door also its hinge end, a point in its swing and its leaf's length."""
    return [_window(w, scale_mm, page_height) for w in found.windows] + [
        _door(d, scale_mm, page_height) for d in found.doors
    ]


def beyond_symbols(
    model: Sequence[ExtractedElement], drawn: Sequence[ExtractedElement], reach_px: float
) -> list[ExtractedElement]:
    """The floor-plan model's objects, less its doors and windows that lie within
    `reach_px` of one read from the drawing's own symbols: there, the ink's shape wins."""
    centres = [
        _centre(e.bbox) for e in drawn if e.kind in ("door", "window") and e.bbox is not None
    ]
    return [
        e
        for e in model
        if e.kind not in ("door", "window")
        or e.bbox is None
        or all(float(np.hypot(*np.subtract(_centre(e.bbox), c))) > reach_px for c in centres)
    ]


def _centre(b: BBox) -> Point:
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def _window(w: Window, scale_mm: float | None, page_height: float) -> ExtractedElement:
    x0, y0, x1, y1 = (float(v) for v in w.box)
    polygon: list[Point] = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    properties: dict[str, object] = {"thickness_px": w.thickness_px}
    return _opening("window", w.a, w.b, polygon, properties, scale_mm, page_height)


def _door(d: Door, scale_mm: float | None, page_height: float) -> ExtractedElement:
    # The leaf, the gap and the arc between them: the triangle hinge, free end, leaf end.
    polygon: list[Point] = [d.a, d.b, d.leaf]
    properties: dict[str, object] = {
        "hinge": "a",
        "toward": [round(v, 2) for v in d.toward],
        "radius_px": round(d.radius_px, 2),
    }
    el = _opening("door", d.a, d.b, polygon, properties, scale_mm, page_height)
    # The box round the leaf and the swing: the hinge's quarter square.
    corner = (d.b[0] + d.leaf[0] - d.a[0], d.b[1] + d.leaf[1] - d.a[1])
    xs, ys = (d.a[0], d.b[0], d.leaf[0], corner[0]), (d.a[1], d.b[1], d.leaf[1], corner[1])
    el.bbox = (min(xs), min(ys), max(xs), max(ys))
    return el


def _opening(
    kind: str,
    a: Point,
    b: Point,
    polygon: list[Point],
    properties: dict[str, object],
    scale_mm: float | None,
    page_height: float,
) -> ExtractedElement:
    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
    el = ExtractedElement(
        kind=kind,
        source="derived",
        bbox=(min(xs), min(ys), max(xs), max(ys)),
        confidence=SYMBOL_CONFIDENCE,
        properties={
            "opening": {"a": [round(v, 2) for v in a], "b": [round(v, 2) for v in b]},
            **properties,
            "polygon_px": [[round(v, 2) for v in p] for p in polygon],
        },
    )
    if scale_mm:
        el.footprint_mm = footprint_mm(polygon, scale_mm, page_height)
        el.value_mm = round(float(np.hypot(b[0] - a[0], b[1] - a[1])) * scale_mm, 2)
    return el
