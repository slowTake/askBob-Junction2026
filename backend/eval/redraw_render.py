"""Masks for the redraw benchmark (#131): draw walls as pixels, compare two masks.

Scoring by pixels needs no matching: a wall split into two runs, or two runs drawn as
one band, covers the same pixels. `near_share` asks how much of one mask lies within a
tolerance of the other, so a line one or two pixels beside its truth still counts:
the truth is drawn by hand, and a scan's lines are a few pixels wide.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass

import cv2
import numpy as np

from app.domain.geometry import Point
from eval.redraw_sheet import Fixture, Opening, Wall

Mask = np.ndarray  # bool, shape (height, width)


@dataclass(frozen=True)
class MaskScore:
    recall: float  # share of the truth within the tolerance of the redraw
    precision: float  # share of the redraw within the tolerance of the truth

    @property
    def f1(self) -> float:
        total = self.recall + self.precision
        return 2 * self.recall * self.precision / total if total else 0.0


def wall_mask(walls: Iterable[Wall], width: int, height: int) -> Mask:
    """The walls filled in, on a `width` x `height` page; parts off the page are clipped."""
    canvas = np.zeros((height, width), dtype=np.uint8)
    for w in walls:
        # One call per wall: given several outlines at once, fillPoly leaves their overlap
        # empty (even-odd), which would cut a hole at every junction.
        cv2.fillPoly(canvas, [np.round(np.array(w.polygon)).astype(np.int32)], 1)
    return canvas.astype(bool)


def opening_mask(openings: Iterable[Opening], width: int, height: int) -> Mask:
    """Doors and windows as the Redrawn view draws them, 1 px lines (D-055): a door with a
    swing is its leaf (from the hinge, as long as the gap, into the room it opens into)
    and the quarter arc back to the gap's free end; a window with a frame is the frame's
    outline; anything else is its gap's line."""
    canvas = np.zeros((height, width), dtype=np.uint8)
    for o in openings:
        if o.kind == "door" and o.hinge is not None and o.toward is not None:
            _door(canvas, o.a, o.b, o.hinge, o.toward)
        elif o.frame:
            outline = np.round(np.array(o.frame)).astype(np.int32)
            cv2.polylines(canvas, [outline], isClosed=True, color=1, thickness=1)
        else:
            cv2.line(canvas, _px(o.a), _px(o.b), 1, 1)
    return canvas.astype(bool)


def fixture_mask(fixtures: Iterable[Fixture], width: int, height: int) -> Mask:
    """Fixtures as the Redrawn view draws them (#146): their closed outline, 1 px."""
    canvas = np.zeros((height, width), dtype=np.uint8)
    for f in fixtures:
        outline = np.round(np.array(f.polygon)).astype(np.int32)
        cv2.polylines(canvas, [outline], isClosed=True, color=1, thickness=1)
    return canvas.astype(bool)


def _door(canvas: np.ndarray, a: Point, b: Point, hinge: Point, toward: Point) -> None:
    free = b if math.dist(hinge, a) <= math.dist(hinge, b) else a
    radius = math.dist(hinge, free)
    if radius == 0:
        return
    ux, uy = (free[0] - hinge[0]) / radius, (free[1] - hinge[1]) / radius
    nx, ny = -uy, ux  # across the wall; flipped to the side the door opens into
    if nx * (toward[0] - hinge[0]) + ny * (toward[1] - hinge[1]) < 0:
        nx, ny = -nx, -ny
    leaf = (hinge[0] + radius * nx, hinge[1] + radius * ny)
    cv2.line(canvas, _px(hinge), _px(leaf), 1, 1)
    start = math.degrees(math.atan2(ny, nx))
    end = math.degrees(math.atan2(uy, ux))
    if (end - start) % 360 > 180:  # always the quarter between the two, in either order
        start, end = end, start
    sweep = (end - start) % 360
    r = round(radius)
    cv2.ellipse(canvas, _px(hinge), (r, r), 0, start, start + sweep, 1, 1)


def _px(p: Point) -> tuple[int, int]:
    return round(p[0]), round(p[1])


def near_share(source: Mask, target: Mask, tolerance_px: float) -> float:
    """Share of `source` pixels within `tolerance_px` (straight line) of a `target` pixel.

    1.0 when `source` is empty: there was nothing to cover.
    """
    count = int(source.sum())
    if count == 0:
        return 1.0
    if not target.any():
        return 0.0
    # Distance from every pixel to the nearest target pixel (the zeros of the input).
    away = cv2.distanceTransform((~target).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    return int((away[source] <= tolerance_px).sum()) / count


def mask_scores(redraw: Mask, truth: Mask, tolerance_px: float) -> MaskScore:
    return MaskScore(
        recall=near_share(truth, redraw, tolerance_px),
        precision=near_share(redraw, truth, tolerance_px),
    )
