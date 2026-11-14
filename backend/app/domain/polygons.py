"""Polygon and box helpers for CAD and vector geometry."""

import math
from collections.abc import Callable, Sequence

from app.domain.geometry import BBox, Point, polygon_area


def point_in_polygon(p: Point, polygon: list[Point]) -> bool:
    """Ray casting. Points exactly on an edge may land either way."""
    x, y = p
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_cross:
                inside = not inside
    return inside


def polygon_bbox(polygon: list[Point]) -> BBox:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def cluster_boxes(boxes: Sequence[BBox], gap: float) -> list[list[int]]:
    """Group boxes that overlap or lie within `gap` of each other (transitively).

    A negative gap demands a real overlap: boxes that merely touch stay apart.
    Returns index groups, each sorted, ordered by their first index.
    """

    def near(i: int, j: int) -> bool:
        a, b = boxes[i], boxes[j]
        return (
            a[0] - gap <= b[2] and b[0] - gap <= a[2] and a[1] - gap <= b[3] and b[1] - gap <= a[3]
        )

    return _components(len(boxes), near)


def cluster_by_endpoints(ends: list[tuple[Point, Point]], tolerance: float) -> list[list[int]]:
    """Group open curves that share exactly one endpoint (within `tolerance`), transitively.

    The two swing arcs of a double door meet where the closed leaves meet. Curves
    sharing both endpoints are the same arc drawn twice and stay separate (the
    dataset's answer key counts those as two doors).
    """

    def near(i: int, j: int) -> bool:
        shared = sum(1 for p in ends[i] if any(math.dist(p, q) <= tolerance for q in ends[j]))
        return shared == 1

    return _components(len(ends), near)


def _components(n: int, near: Callable[[int, int], bool]) -> list[list[int]]:
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if near(i, j):
                parent[find(i)] = find(j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return sorted(groups.values(), key=lambda g: g[0])


def path_polygon(ops: list[tuple[str, list[Point]]]) -> list[Point]:
    """Vertices of a vector path given as (operator, points) pairs.

    "l" (line) and "c" (curve) contribute their start point; curves are reduced to
    their end points, which is fine for wall outlines. "re" (rectangle, given as
    two opposite corners) becomes four corners. A final point equal to the first
    is dropped.
    """
    out: list[Point] = []
    for op, pts in ops:
        if op == "re":
            (x0, y0), (x1, y1) = pts[0], pts[-1]
            out += [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        elif pts:
            out.append(pts[0])
            last = pts[-1]
    if ops and ops[-1][0] != "re" and out and math.dist(last, out[0]) > 1e-6:
        out.append(last)
    return out


def clean_polygon(points: Sequence[Point], tolerance: float) -> list[Point] | None:
    """Drop repeated vertices (within `tolerance`) and a closing duplicate of the first.

    Returns None when fewer than 3 vertices remain or the shape has no area, so
    callers never build geometry from a degenerate outline.
    """
    out: list[Point] = []
    for p in points:
        if not out or math.dist(p, out[-1]) > tolerance:
            out.append((float(p[0]), float(p[1])))
    if len(out) > 1 and math.dist(out[0], out[-1]) <= tolerance:
        out.pop()
    if len(out) < 3 or polygon_area(out) <= tolerance * tolerance:
        return None
    return out
