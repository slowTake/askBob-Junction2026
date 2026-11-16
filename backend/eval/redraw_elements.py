"""The app's redraw of a page as a benchmark `Sheet` (#131).

Mirrors `frontend/src/lib/redraw.ts` `buildCleanSheet` rule for rule, so the benchmark
scores exactly what the Redrawn view draws. Keep the two in step.

Takes the app's `ExtractedElement`s (what ingest returns; the stored `ElementInfo` has the
same fields). Elements without a box of positive area are not drawn. Then:
- a wall: its `properties.polygon_px` when that is a polygon of finite numbers, else its box;
- a door or window: its box, read as the centre line along the box's long side (a square
  box counts as horizontal). The view draws a box, so there is no hinge or swing;
- a room: its label (else its text), trimmed, at the box centre, with `polygon_px` as its
  outline. A computed `area_m2` is drawn under the name unless the drawing prints an area
  inside the room's outline;
- any other kind: its label (else text) at the box centre. Unclassified `text` is kept
  only from `MIN_TEXT_CONFIDENCE` and with a letter or digit.
Text kinds: the app's `dimension` and `height` keep their kind, everything else -> "other".
The view draws every label level, so rotation is always 0.
"""

import math
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import TypeGuard

from app.domain.geometry import BBox, Point
from app.ingest.types import ExtractedElement
from eval.redraw_sheet import Opening, Room, Sheet, Text, Wall

TEXT_SHARE = 1 / 100  # text size as a share of the page width (redraw.ts)
ROOM_SIZE = 1.5  # room names relative to other text
AREA_LINE = 1  # the area line sits one name-height below the name
MIN_TEXT_CONFIDENCE = 0.6  # unclassified OCR text below this is not drawn
_SCORED_KINDS = ("dimension", "height")  # app kinds the truth also has


def sheet_from_elements(elements: Sequence[ExtractedElement], page_width: float) -> Sheet:
    """What the Redrawn view draws for these elements on a page `page_width` px wide."""
    room_size = ROOM_SIZE * page_width * TEXT_SHARE
    printed_areas = [_centre(e.bbox) for e in elements if e.kind == "area" and _has_area(e.bbox)]
    walls: list[Wall] = []
    openings: list[Opening] = []
    rooms: list[Room] = []
    texts: list[Text] = []
    for e in elements:
        if e.bbox is None or not _has_area(e.bbox):
            continue
        x0, y0, x1, y1 = e.bbox
        if e.kind == "wall":
            box = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
            walls.append(Wall(_polygon(e.properties.get("polygon_px")) or box))
            continue
        if e.kind in ("door", "window"):
            openings.append(_opening(e.kind, e.bbox))
            continue
        # JS `label ?? text ?? ""`: an empty label does not fall back to the text.
        raw = e.label if e.label is not None else e.text if e.text is not None else ""
        text = raw.strip()
        if not text:
            continue
        if e.kind == "text" and not _legible(text, e.confidence):
            continue
        cx, cy = _centre(e.bbox)
        if e.kind == "room":
            outline = _polygon(e.properties.get("polygon_px"))
            rooms.append(Room(text, (cx, cy), outline))
            area = _room_area(e.properties.get("area_m2"), outline, printed_areas)
            if area is not None:
                texts.append(Text(area, "other", (cx, cy + AREA_LINE * room_size)))
            continue
        texts.append(Text(text, e.kind if e.kind in _SCORED_KINDS else "other", (cx, cy)))
    return Sheet(tuple(walls), tuple(openings), tuple(rooms), tuple(texts))


def _opening(kind: str, b: BBox) -> Opening:
    x0, y0, x1, y1 = b
    cx, cy = _centre(b)
    if x1 - x0 >= y1 - y0:
        return Opening(kind, (x0, cy), (x1, cy))
    return Opening(kind, (cx, y0), (cx, y1))


def _polygon(raw: object) -> tuple[Point, ...] | None:
    """redraw.ts `polygonPoints`: at least three [x, y] pairs of finite numbers, else None."""
    if not isinstance(raw, list | tuple) or len(raw) < 3:
        return None
    points: list[Point] = []
    for p in raw:
        if not isinstance(p, list | tuple) or len(p) != 2 or not all(_finite(v) for v in p):
            return None
        points.append((float(p[0]), float(p[1])))
    return tuple(points)


def _room_area(m2: object, outline: tuple[Point, ...] | None, printed: list[Point]) -> str | None:
    if not _finite(m2):
        return None
    if outline and any(_inside(outline, x, y) for x, y in printed):
        return None
    # JS toFixed(1) rounds a tie up; Decimal of the float is its exact binary value, as there.
    return f"{Decimal(float(m2)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)} m²"


def _inside(poly: tuple[Point, ...], x: float, y: float) -> bool:
    """redraw.ts `insidePolygon`: ray casting to the right."""
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        (xi, yi), (xj, yj) = poly[i], poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _legible(text: str, confidence: float) -> bool:
    """Read with some certainty, and more than punctuation (JS /[\\p{L}\\p{N}]/u)."""
    return confidence >= MIN_TEXT_CONFIDENCE and any(c.isalpha() or c.isnumeric() for c in text)


def _centre(b: BBox | None) -> Point:
    assert b is not None
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def _has_area(b: BBox | None) -> bool:
    return b is not None and b[2] > b[0] and b[3] > b[1]


def _finite(v: object) -> TypeGuard[float]:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)
