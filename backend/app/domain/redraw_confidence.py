"""How much of a page's own ink the Redrawn view accounts for (#132).

A benchmark has an answer key; an upload has only its pixels. This score compares what
the Redrawn view draws with the page's line work, so it needs no truth:

- **covered**: the share of the ink that lies within a tolerance of something drawn.
  What is left is *missed* ink (a wall, a label, a fixture the redraw does not have).
- **on ink**: the share of what is drawn that lies within the tolerance of ink. What is
  left is *added*: drawn on blank paper.
- **score**: the harmonic mean of the two, so a redraw cannot buy coverage by painting
  the page black, or precision by drawing nothing.

The redraw is drawn as pixels the way the view draws it (`drawn_shape`, mirroring
`frontend/src/lib/redraw.ts`): walls as their outlines; doors and windows from their
stored gap (D-055): a door with a swing as its leaf and arc, a window as its frame, any
other gap as its line, all drawn as 1 px lines, and as their box without a gap; a
fixture traced from the ink (#146) as its closed outline, 1 px (a coded one is a label);
labels
as a box of the rendered text's size at the element's centre: the view uses one font
size per page, never the OCR box, so a misread box does not score.
The breakdown is per part. The pixel work is in `app/ingest/confidence.py`; this module
is the rules and the stored shape, pure.
"""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol, TypeGuard

from app.domain.geometry import BBox, Point

CONFIDENCE_KEY = "redraw_confidence"  # page.meta key
CONFIDENCE_FORMAT = 2  # bumped when the rules change, so an older entry is not served
# Share of the page width within which a drawn pixel is on the ink: 2 px on the
# benchmark's 482 px page, the same as its wall and ink tolerance (D-049).
INK_TOLERANCE = 2 / 482
PARTS = ("walls", "openings", "fixtures", "rooms", "dimensions", "heights", "text")
MARK_CAP = 40  # patches of missed or added pixels kept, the largest first

# redraw.ts: one text size per page, room names 1.5x, unsure free text not drawn.
TEXT_SHARE = 1 / 100
ROOM_SIZE = 1.5
MIN_TEXT_CONFIDENCE = 0.6
GLYPH_WIDTH = 0.6  # em: the average advance of the view's font
ARC_STEP_DEG = 5  # a door's arc is drawn as a line through a point every 5 degrees


@dataclass(frozen=True)
class Shape:
    part: str
    polygon: tuple[Point, ...]
    stroke: bool = False  # drawn as a 1 px line through its points, not filled


@dataclass(frozen=True)
class PartScore:
    count: int  # elements drawn
    drawn_px: int  # pixels the part covers
    on_ink: float  # share of them on ink (1.0 when nothing is drawn)
    ink_covered: float  # share of the page's ink within the tolerance of this part


@dataclass(frozen=True)
class Mark:
    """A patch of missed or added pixels: its outline (page px) and how many it holds."""

    polygon: tuple[Point, ...]
    px: int


@dataclass(frozen=True)
class RedrawConfidence:
    score: float
    covered: float
    on_ink: float
    ink_px: int
    parts: Mapping[str, PartScore]
    missed: tuple[Mark, ...]
    added: tuple[Mark, ...]


class Drawn(Protocol):
    """What the view reads of an element: ingest's `ExtractedElement` or a stored row."""

    @property
    def kind(self) -> str: ...
    @property
    def bbox(self) -> Any: ...  # a 4-sequence of numbers, or None
    @property
    def label(self) -> str | None: ...
    @property
    def text(self) -> str | None: ...
    @property
    def confidence(self) -> float: ...
    @property
    def properties(self) -> Mapping[str, Any]: ...


def score(covered: float, on_ink: float) -> float:
    total = covered + on_ink
    return 2 * covered * on_ink / total if total else 0.0


def shapes_of(elements: Iterable[Drawn], page_width: float) -> list[Shape]:
    """Everything the view draws for these elements, on a page `page_width` px wide."""
    shapes = []
    for e in elements:
        box = _box(e.bbox)
        if e.bbox is not None and box is None:
            continue  # not four numbers: nothing the view can draw
        shape = drawn_shape(e.kind, box, e.label, e.text, e.confidence, e.properties, page_width)
        if shape is not None:
            shapes.append(shape)
    return shapes


def drawn_shape(
    kind: str,
    bbox: BBox | None,
    label: str | None,
    text: str | None,
    confidence: float,
    properties: Mapping[str, object],
    page_width: float,
) -> Shape | None:
    """What the Redrawn view draws for an element, as a polygon, or None if nothing."""
    if bbox is None or not (bbox[2] > bbox[0] and bbox[3] > bbox[1]):
        return None
    x0, y0, x1, y1 = bbox
    box: tuple[Point, ...] = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    if kind == "wall":
        return Shape("walls", _polygon(properties.get("polygon_px")) or box)
    if kind in ("door", "window"):
        line = _stored_opening(kind, properties)
        return Shape("openings", line, stroke=True) if line else Shape("openings", box)
    outline = _polygon(properties.get("polygon_px")) if kind == "fixture" else None
    if outline:
        return Shape("fixtures", (*outline, outline[0]), stroke=True)
    # JS `label ?? text ?? ""`: an empty label does not fall back to the text.
    raw = label if label is not None else text if text is not None else ""
    shown = raw.strip()
    if not shown:
        return None
    if kind == "text" and not _legible(shown, confidence):
        return None
    size = page_width * TEXT_SHARE
    if kind == "room":
        part, size = "rooms", size * ROOM_SIZE
    elif kind in ("dimension", "height"):
        part = kind + "s"
    else:
        part = "text"
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half_w, half_h = GLYPH_WIDTH * size * len(shown) / 2, size / 2
    return Shape(
        part,
        ((cx - half_w, cy - half_h), (cx + half_w, cy - half_h),
         (cx + half_w, cy + half_h), (cx - half_w, cy + half_h)),
    )  # fmt: skip


def _stored_opening(kind: str, properties: Mapping[str, object]) -> tuple[Point, ...] | None:
    """redraw.ts `storedOpening`, as one line: a door's leaf then its arc, a window's
    frame closed, or the gap; None without a gap of two points."""
    raw = properties.get("opening")
    if not isinstance(raw, Mapping):
        return None
    a, b = _point(raw.get("a")), _point(raw.get("b"))
    if a is None or b is None:
        return None
    hinge = {"a": a, "b": b}.get(str(properties.get("hinge")))
    toward = _point(properties.get("toward"))
    if kind == "door" and hinge is not None and toward is not None:
        swing = _swing(hinge, b if hinge is a else a, toward)
        if swing:
            return swing
    frame = _polygon(properties.get("polygon_px")) if kind == "window" else None
    if frame:
        return (*frame, frame[0])
    return (a, b)


def _swing(hinge: Point, free: Point, toward: Point) -> tuple[Point, ...] | None:
    """The hinge, the leaf's end turned open toward `toward`, and the arc back to `free`."""
    r = math.dist(hinge, free)
    if r == 0:
        return None
    ux, uy = (free[0] - hinge[0]) / r, (free[1] - hinge[1]) / r
    nx, ny = -uy, ux
    if nx * (toward[0] - hinge[0]) + ny * (toward[1] - hinge[1]) < 0:
        nx, ny = -nx, -ny
    start = math.atan2(ny, nx)
    turn = math.atan2(nx * uy - ny * ux, nx * ux + ny * uy)  # +-90 degrees, leaf to gap
    steps = round(abs(math.degrees(turn)) / ARC_STEP_DEG)
    arc = tuple(
        (hinge[0] + r * math.cos(start + turn * i / steps),
         hinge[1] + r * math.sin(start + turn * i / steps))
        for i in range(1, steps + 1)
    )  # fmt: skip
    return (hinge, (hinge[0] + r * nx, hinge[1] + r * ny), *arc[:-1], free)


def _point(raw: object) -> Point | None:
    if isinstance(raw, list | tuple) and len(raw) == 2 and all(_finite(v) for v in raw):
        return (float(raw[0]), float(raw[1]))
    return None


def _box(raw: object) -> BBox | None:
    if not isinstance(raw, list | tuple) or len(raw) != 4 or not all(_finite(v) for v in raw):
        return None
    return (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))


def confidence_meta(c: RedrawConfidence) -> dict[str, Any]:
    """What `page.meta["redraw_confidence"]` stores: shares to 3 decimals, outlines as ints."""
    return {
        "format": CONFIDENCE_FORMAT,
        "score": round(c.score, 3),
        "covered": round(c.covered, 3),
        "on_ink": round(c.on_ink, 3),
        "ink_px": c.ink_px,
        "parts": {
            part: {
                "count": p.count,
                "drawn_px": p.drawn_px,
                "on_ink": round(p.on_ink, 3),
                "ink_covered": round(p.ink_covered, 3),
            }
            for part, p in c.parts.items()
        },
        "missed": [_mark_meta(m) for m in c.missed],
        "added": [_mark_meta(m) for m in c.added],
    }


def confidence_from_meta(raw: object) -> dict[str, Any] | None:
    """The stored entry as the API serves it; None when missing, older or malformed."""
    if not isinstance(raw, Mapping) or raw.get("format") != CONFIDENCE_FORMAT:
        return None
    if not all(_share(raw.get(k)) for k in ("score", "covered", "on_ink")):
        return None
    if not isinstance(raw.get("ink_px"), int) or not isinstance(raw.get("parts"), Mapping):
        return None
    if not all(isinstance(raw.get(k), list) for k in ("missed", "added")):
        return None
    return {k: v for k, v in raw.items() if k != "format"}


def _mark_meta(m: Mark) -> dict[str, Any]:
    return {"polygon": [[round(x), round(y)] for x, y in m.polygon], "px": m.px}


def _share(v: object) -> TypeGuard[float]:
    return isinstance(v, int | float) and not isinstance(v, bool) and 0 <= v <= 1


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


def _legible(text: str, confidence: float) -> bool:
    """Read with some certainty, and more than punctuation (JS /[\\p{L}\\p{N}]/u)."""
    return confidence >= MIN_TEXT_CONFIDENCE and any(c.isalpha() or c.isnumeric() for c in text)


def _finite(v: object) -> TypeGuard[float]:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)
