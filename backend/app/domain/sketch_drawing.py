"""What a tidied sketch plan looks like: the shapes the redraw draws, in page pixels.

The same shapes are rendered on the server (for the model to check its draft) and
stored on the elements (for the frontend to draw), so what the model checks is what
the user sees. Sizes are shares of the page's longer side; none is a real length.

- wall: a filled band with square ends, cut where a door or window sits on it
- door: the leaf drawn open, at right angles to the wall, and a quarter-circle swing
- window: a thin double line across the wall, with a tick at each end
- room name and written text: one size each, centred on their point
"""

import math
from dataclasses import dataclass
from typing import Any

from app.domain.geometry import BBox, Point
from app.domain.sketch import Door, Plan, Room, Wall, Window

OUTER_SHARE = 0.012  # outer wall thickness
INNER_SHARE = 0.007  # inner wall thickness
ROOM_FONT_SHARE = 0.024
NOTE_FONT_SHARE = 0.016
CHAR_WIDTH = 0.6  # of the font size, for a label's box
ARC_STEPS = 12
ON_WALL_PX = 0.5  # an opening this close to a wall's line sits on it

Pts = list[list[float]]


@dataclass(frozen=True)
class Shape:
    """One element to store: its kind, text, box and drawing (in `properties`)."""

    kind: str
    text: str | None
    bbox: BBox
    properties: dict[str, Any]


def sketch_shapes(plan: Plan, width: float, height: float) -> list[Shape]:
    side = max(width, height)
    outer, inner = OUTER_SHARE * side, INNER_SHARE * side
    openings = [(d.a, d.b) for d in plan.doors] + [(w.a, w.b) for w in plan.windows]
    shapes = [_wall(w, outer if w.outer else inner, openings) for w in plan.walls]
    shapes += [_door(d) for d in plan.doors]
    shapes += [_window(w, _host_width(w, plan.walls, outer, inner)) for w in plan.windows]
    shapes += [_room(r, ROOM_FONT_SHARE * side) for r in plan.rooms]
    font = NOTE_FONT_SHARE * side
    shapes += [
        Shape(
            "text",
            n.text,
            _label_box(n.at, n.text, font),
            {"label_px": _pt(n.at), "font_px": _r(font), "written": True},
        )
        for n in plan.notes
    ]
    return shapes


def _wall(wall: Wall, thickness: float, openings: list[tuple[Point, Point]]) -> Shape:
    a, b = wall.a, wall.b
    length = math.dist(a, b)
    half = thickness / 2
    gaps = sorted(
        span for oa, ob in openings if (span := _span_on(oa, ob, a, b, length)) is not None
    )
    pieces: list[tuple[float, float]] = []
    start = -half
    for g0, g1 in gaps:
        if g0 > start:
            pieces.append((start, g0))
        start = max(start, g1)
    if length + half > start:
        pieces.append((start, length + half))
    polygon = _band(a, b, length, -half, length + half, half)
    return Shape(
        "wall",
        None,
        _bounds(polygon),
        {
            "segment_px": [_pt(a), _pt(b)],
            "thickness": "outer" if wall.outer else "inner",
            "width_px": _r(thickness),
            "polygon_px": polygon,
            "pieces_px": [_band(a, b, length, t0, t1, half) for t0, t1 in pieces],
        },
    )


def _door(door: Door) -> Shape:
    hinge, free = (door.a, door.b) if door.hinge_at_a else (door.b, door.a)
    radius = math.dist(hinge, free)
    ux, uy = (free[0] - hinge[0]) / radius, (free[1] - hinge[1]) / radius
    nx, ny = -uy, ux
    if nx * (door.toward[0] - hinge[0]) + ny * (door.toward[1] - hinge[1]) < 0:
        nx, ny = -nx, -ny
    leaf = (hinge[0] + nx * radius, hinge[1] + ny * radius)
    t0 = math.atan2(leaf[1] - hinge[1], leaf[0] - hinge[0])
    t1 = math.atan2(free[1] - hinge[1], free[0] - hinge[0])
    sweep = (t1 - t0 + math.pi) % (2 * math.pi) - math.pi  # the quarter turn, signed
    arc = [
        (hinge[0] + radius * math.cos(t0 + sweep * i / ARC_STEPS),
         hinge[1] + radius * math.sin(t0 + sweep * i / ARC_STEPS))
        for i in range(1, ARC_STEPS)
    ]  # fmt: skip
    arc_px = [_pt(leaf), *(_pt(p) for p in arc), _pt(free)]
    return Shape(
        "door",
        None,
        _bounds([_pt(door.a), _pt(door.b), *arc_px]),
        {
            "opening_px": [_pt(door.a), _pt(door.b)],
            "hinge_px": _pt(hinge),
            "leaf_px": [_pt(hinge), _pt(leaf)],
            "arc_px": arc_px,
        },
    )


def _window(window: Window, wall_width: float) -> Shape:
    a, b = window.a, window.b
    length = math.dist(a, b)
    nx, ny = -(b[1] - a[1]) / length, (b[0] - a[0]) / length

    def off(p: Point, k: float) -> list[float]:
        return _pt((p[0] + nx * k, p[1] + ny * k))

    q, h = wall_width / 4, wall_width / 2
    lines = [[off(a, q), off(b, q)], [off(a, -q), off(b, -q)],
             [off(a, h), off(a, -h)], [off(b, h), off(b, -h)]]  # fmt: skip
    return Shape(
        "window",
        None,
        _bounds([p for line in lines for p in line]),
        {"opening_px": [_pt(a), _pt(b)], "lines_px": lines},
    )


def _room(room: Room, font: float) -> Shape:
    properties: dict[str, Any] = {"label_px": _pt(room.label), "font_px": _r(font)}
    box = _label_box(room.label, room.name, font)
    if room.outline:
        polygon = [_pt(p) for p in room.outline]
        properties |= {"polygon_px": polygon, "outline": "approximate"}
        box = _bounds(polygon)
    return Shape("room", room.name, box, properties)


def _host_width(window: Window, walls: tuple[Wall, ...], outer: float, inner: float) -> float:
    for w in walls:
        if _span_on(window.a, window.b, w.a, w.b, math.dist(w.a, w.b)) is not None:
            return outer if w.outer else inner
    return inner


def _span_on(oa: Point, ob: Point, a: Point, b: Point, length: float) -> tuple[float, float] | None:
    """Where an opening lies along the wall a-b (distance from a), if it is on it."""
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    spans = []
    for p in (oa, ob):
        rx, ry = p[0] - a[0], p[1] - a[1]
        if abs(rx * uy - ry * ux) > ON_WALL_PX:
            return None
        spans.append(rx * ux + ry * uy)
    t0, t1 = sorted(spans)
    if t1 < -ON_WALL_PX or t0 > length + ON_WALL_PX:
        return None
    return (t0, t1)


def _band(a: Point, b: Point, length: float, t0: float, t1: float, half: float) -> Pts:
    """The rectangle from t0 to t1 along a-b, `half` either side of the line."""
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    nx, ny = -uy, ux
    s = (a[0] + ux * t0, a[1] + uy * t0)
    e = (a[0] + ux * t1, a[1] + uy * t1)
    return [
        _pt((s[0] + nx * half, s[1] + ny * half)),
        _pt((e[0] + nx * half, e[1] + ny * half)),
        _pt((e[0] - nx * half, e[1] - ny * half)),
        _pt((s[0] - nx * half, s[1] - ny * half)),
    ]


def _label_box(at: Point, text: str, font: float) -> BBox:
    half_w, half_h = CHAR_WIDTH * font * len(text) / 2, font / 2
    return (_r(at[0] - half_w), _r(at[1] - half_h), _r(at[0] + half_w), _r(at[1] + half_h))


def _bounds(points: Pts) -> BBox:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _pt(p: Point) -> list[float]:
    return [_r(p[0]), _r(p[1])]


def _r(v: float) -> float:
    return round(v, 1) + 0.0  # + 0.0 turns -0.0 into 0.0
