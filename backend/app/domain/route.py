"""A walking route across a plan page, around walls and through doors. Pure.

The page becomes a grid of `cell`-pixel squares: wall boxes and outlines are blocked,
door boxes are carved open (they sit in the wall). The cheapest path costs more next
to walls, so it keeps to the middle of corridors, then is cut down to the corners
where it turns.
"""

import math
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from scipy import ndimage
from skimage import draw
from skimage.graph import MCP_Geometric

BBox = tuple[float, float, float, float]
Point = tuple[float, float]
WALL_PENALTY = 3.0  # extra cost of a step right next to a wall, fading with distance


@dataclass(frozen=True)
class Obstacles:
    walls: list[BBox]  # wall boxes, page px
    wall_polygons: list[list[Point]]  # wall outlines when known, page px
    doors: list[BBox]  # openings carved through the walls


def walkable(size_px: tuple[int, int], obstacles: Obstacles, cell: int) -> np.ndarray:
    """Boolean grid [rows, cols]: True where one can walk."""
    width, height = size_px
    rows, cols = math.ceil(height / cell), math.ceil(width / cell)
    free = np.ones((rows, cols), bool)
    for x0, y0, x1, y1 in obstacles.walls:
        free[_span(y0, y1, cell, rows), _span(x0, x1, cell, cols)] = False
    for polygon in obstacles.wall_polygons:
        ys = [p[1] / cell for p in polygon]
        xs = [p[0] / cell for p in polygon]
        rr, cc = draw.polygon(ys, xs, shape=free.shape)
        free[rr, cc] = False
    for x0, y0, x1, y1 in obstacles.doors:
        free[_span(y0, y1, cell, rows), _span(x0, x1, cell, cols)] = True
    return free


def _span(a: float, b: float, cell: int, limit: int) -> slice:
    lo, hi = sorted((a, b))
    return slice(max(0, int(lo // cell)), min(limit, math.ceil(hi / cell)))


def find_route(free: np.ndarray, start: Point, goal: Point, cell: int) -> list[Point] | None:
    """Corners of the route in page px, start to goal; None if walls separate them."""
    if not free.any():
        return None
    a, b = _snap(free, start, cell), _snap(free, goal, cell)
    clearance = ndimage.distance_transform_edt(free)
    costs = np.where(free, 1.0 + WALL_PENALTY / (1.0 + clearance), np.inf)
    mcp = MCP_Geometric(costs)
    cumulative, _ = mcp.find_costs([a], [b])
    if not np.isfinite(cumulative[b]):
        return None
    cells = mcp.traceback(b)
    # Shortcuts keep a cell of margin, so the drawn line never clips a wall's corner.
    corners = _corners(clearance > 1.0, cells)
    points = [((c + 0.5) * cell, (r + 0.5) * cell) for r, c in corners]
    # Start and end exactly at the given points, unless they were moved out of a wall.
    if a == _cell(start, cell, free):
        points[0] = start
    if b == _cell(goal, cell, free):
        points[-1] = goal
    return points


def _cell(p: Point, cell: int, free: np.ndarray) -> tuple[int, int]:
    rows, cols = free.shape
    return (min(rows - 1, max(0, int(p[1] // cell))), min(cols - 1, max(0, int(p[0] // cell))))


def _snap(free: np.ndarray, p: Point, cell: int) -> tuple[int, int]:
    """The point's cell, or the nearest walkable one when it falls in a wall."""
    r, c = _cell(p, cell, free)
    if free[r, c]:
        return r, c
    _, (ri, ci) = ndimage.distance_transform_edt(~free, return_indices=True)
    return int(ri[r, c]), int(ci[r, c])


def _corners(open_: np.ndarray, cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Keep a cell only when the straight line from the last kept one would leave `open_`."""
    if len(cells) <= 2:
        return list(cells)
    kept = [cells[0]]
    i = 0
    while i < len(cells) - 1:
        j = len(cells) - 1
        while j > i + 1 and not _clear(open_, cells[i], cells[j]):
            j -= 1
        kept.append(cells[j])
        i = j
    return kept


def _clear(free: np.ndarray, a: tuple[int, int], b: tuple[int, int]) -> bool:
    rr, cc = draw.line(a[0], a[1], b[0], b[1])
    return bool(free[rr, cc].all())


def route_length_px(points: list[Point]) -> float:
    return sum(math.dist(p, q) for p, q in pairwise(points))
