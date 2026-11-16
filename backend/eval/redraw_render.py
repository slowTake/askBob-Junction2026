"""Masks for the redraw benchmark (#131): draw walls as pixels, compare two masks.

Scoring by pixels needs no matching: a wall split into two runs, or two runs drawn as
one band, covers the same pixels. `near_share` asks how much of one mask lies within a
tolerance of the other, so a line one or two pixels beside its truth still counts:
the truth is drawn by hand, and a scan's lines are a few pixels wide.
"""

from collections.abc import Iterable
from dataclasses import dataclass

import cv2
import numpy as np

from eval.redraw_sheet import Wall

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
    outlines = [np.round(np.array(w.polygon)).astype(np.int32) for w in walls]
    if outlines:
        cv2.fillPoly(canvas, outlines, 1)
    return canvas.astype(bool)


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
