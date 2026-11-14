"""Tidy a sketch plan in page pixels: straight walls, closed corners, openings on walls.

A hand drawing wobbles. Walls within SNAP_DEGREES of the axes become exactly
horizontal or vertical; wall lines and ends that nearly coincide are moved to one
shared coordinate, so corners close; doors and windows are projected onto their
wall. Everything is relative to the page size: proportions are kept, and nothing is
given a real-world length.
"""

import math
from collections.abc import Iterable, Mapping

from app.domain.geometry import Point
from app.domain.sketch import MIN_LENGTH_PX, Door, Plan, Room, Wall, Window

SNAP_DEGREES = 8.0
JOIN_SHARE = 0.01  # join tolerance as a share of the page's longer side
OPENING_REACH = 2.0  # an opening finds walls up to this many join tolerances away
OPENING_DEGREES = 20.0  # and only walls running roughly the same way

_TAN = math.tan(math.radians(SNAP_DEGREES))


def cluster(values: Iterable[float], tol: float) -> dict[float, float]:
    """Map each value to the mean of its group: sorted values within `tol` of the first."""
    groups: list[list[float]] = []
    for v in sorted(values):
        if groups and v - groups[-1][0] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return {v: sum(g) / len(g) for g in groups for v in g}


def tidy(plan: Plan, width: float, height: float) -> Plan:
    tol = JOIN_SHARE * max(width, height)
    horizontal = [w for w in plan.walls if _axis(w.a, w.b) == "h"]
    vertical = [w for w in plan.walls if _axis(w.a, w.b) == "v"]
    xs = cluster(
        [(w.a[0] + w.b[0]) / 2 for w in vertical] + [p[0] for w in horizontal for p in (w.a, w.b)],
        tol,
    )
    ys = cluster(
        [(w.a[1] + w.b[1]) / 2 for w in horizontal] + [p[1] for w in vertical for p in (w.a, w.b)],
        tol,
    )

    walls: list[Wall] = []
    for w in plan.walls:
        kind = _axis(w.a, w.b)
        if kind == "h":
            y = ys[(w.a[1] + w.b[1]) / 2]
            a, b = (xs[w.a[0]], y), (xs[w.b[0]], y)
        elif kind == "v":
            x = xs[(w.a[0] + w.b[0]) / 2]
            a, b = (x, ys[w.a[1]]), (x, ys[w.b[1]])
        else:
            a, b = _snap(w.a, xs, ys, tol), _snap(w.b, xs, ys, tol)
        if math.dist(a, b) < MIN_LENGTH_PX:
            continue
        _add_wall(walls, Wall(a, b, w.outer))

    reach = OPENING_REACH * tol
    doors = []
    for d in plan.doors:
        placed = _place(d.a, d.b, walls, reach)
        if placed:
            doors.append(Door(placed[0], placed[1], d.hinge_at_a, d.toward))
    windows = []
    for wi in plan.windows:
        placed = _place(wi.a, wi.b, walls, reach)
        if placed:
            windows.append(Window(*placed))
    rooms = tuple(
        Room(
            r.name,
            r.label,
            tuple(_snap(p, xs, ys, tol) for p in r.outline) if r.outline else None,
        )
        for r in plan.rooms
    )
    return Plan(tuple(walls), tuple(doors), tuple(windows), rooms, plan.notes)


def _axis(a: Point, b: Point) -> str:
    dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
    if dy <= _TAN * dx:
        return "h"
    if dx <= _TAN * dy:
        return "v"
    return "d"


def _snap(p: Point, xs: Mapping[float, float], ys: Mapping[float, float], tol: float) -> Point:
    return (_nearest(p[0], xs.values(), tol), _nearest(p[1], ys.values(), tol))


def _nearest(v: float, means: Iterable[float], tol: float) -> float:
    best = min(means, key=lambda m: abs(m - v), default=None)
    return best if best is not None and abs(best - v) <= tol else v


def _add_wall(walls: list[Wall], wall: Wall) -> None:
    """Add `wall` unless the same segment is already there; an outer copy wins."""
    for i, other in enumerate(walls):
        if {other.a, other.b} == {wall.a, wall.b}:
            walls[i] = Wall(other.a, other.b, other.outer or wall.outer)
            return
    walls.append(wall)


def _place(a: Point, b: Point, walls: list[Wall], reach: float) -> tuple[Point, Point] | None:
    """The opening on its nearest wall running the same way, or straightened if none."""
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    best: tuple[float, Wall] | None = None
    for w in walls:
        if _angle(a, b, w.a, w.b) > OPENING_DEGREES:
            continue
        gap = _distance_to_segment(mid, w.a, w.b)
        if gap <= reach and (best is None or gap < best[0]):
            best = (gap, w)
    if best is None:
        kind = _axis(a, b)
        if kind == "h":
            y = (a[1] + b[1]) / 2
            return (a[0], y), (b[0], y)
        if kind == "v":
            x = (a[0] + b[0]) / 2
            return (x, a[1]), (x, b[1])
        return a, b
    wall = best[1]
    pa, pb = _project(a, wall), _project(b, wall)
    return (pa, pb) if math.dist(pa, pb) >= MIN_LENGTH_PX else None


def _angle(a: Point, b: Point, c: Point, d: Point) -> float:
    """Angle between two lines in degrees, 0 to 90."""
    t1 = math.atan2(b[1] - a[1], b[0] - a[0])
    t2 = math.atan2(d[1] - c[1], d[0] - c[0])
    diff = abs(math.degrees(t1 - t2)) % 180
    return min(diff, 180 - diff)


def _param(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    return ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)


def _distance_to_segment(p: Point, a: Point, b: Point) -> float:
    t = max(0.0, min(1.0, _param(p, a, b)))
    return math.dist(p, (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))


def _project(p: Point, wall: Wall) -> Point:
    a, b = wall.a, wall.b
    t = max(0.0, min(1.0, _param(p, a, b)))
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
