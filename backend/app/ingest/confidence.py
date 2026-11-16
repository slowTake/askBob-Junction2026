"""Score a page's redraw against its own ink, pixel by pixel (#132).

The rules and the stored shape are in `app/domain/redraw_confidence.py`. Here the
drawn shapes become masks, one per part, and are compared with the page's ink the way
the benchmark compares walls (`eval/redraw_render.py`): a pixel counts when it lies
within the tolerance (straight-line distance) of the other mask. The ink is the colour
layers' line work plus the red annotations (D-051): height labels are red on colorful-34
and the redraw is meant to carry them; fills are paper.

Missed and added pixels are returned as outlines the view can draw: each patch is grown
by the tolerance, so a thin stroke becomes a visible halo, and only the largest patches
are kept. Pure: arrays in, a dataclass out.
"""

from collections.abc import Sequence

import cv2
import numpy as np

from app.domain.redraw_confidence import (
    INK_TOLERANCE,
    MARK_CAP,
    PARTS,
    Mark,
    PartScore,
    RedrawConfidence,
    Shape,
    score,
)
from app.ingest.ink import ColourLayers
from app.ingest.rooms import Mask


def page_ink(layers: ColourLayers) -> Mask:
    """The ink the redraw is scored against: line work and red annotations."""
    return layers.ink | layers.annotations


def score_redraw(layers: ColourLayers, shapes: Sequence[Shape]) -> RedrawConfidence:
    """The confidence of a redraw of `shapes` on a page with these colour layers."""
    ink = page_ink(layers)
    return redraw_confidence(ink, shapes, INK_TOLERANCE * ink.shape[1])


def redraw_confidence(
    ink: Mask, shapes: Sequence[Shape], tolerance_px: float, cap: int = MARK_CAP
) -> RedrawConfidence:
    """Score `shapes` (page px) against the `ink` mask, within `tolerance_px`."""
    height, width = ink.shape
    masks = {part: _mask([s for s in shapes if s.part == part], width, height) for part in PARTS}
    drawn = np.zeros_like(ink)
    for m in masks.values():
        drawn |= m
    ink_px = int(ink.sum())
    away_from_ink = _distance(ink)
    away_from_drawn = _distance(drawn)
    covered = _near_share(ink, away_from_drawn, tolerance_px)
    on_ink = _near_share(drawn, away_from_ink, tolerance_px)
    parts = {
        part: PartScore(
            count=sum(1 for s in shapes if s.part == part),
            drawn_px=int(m.sum()),
            on_ink=_near_share(m, away_from_ink, tolerance_px),
            ink_covered=_covered_by(ink, ink_px, m, tolerance_px),
        )
        for part, m in masks.items()
    }
    return RedrawConfidence(
        score=score(covered, on_ink),
        covered=covered,
        on_ink=on_ink,
        ink_px=ink_px,
        parts=parts,
        missed=_marks(ink & (away_from_drawn > tolerance_px), tolerance_px, cap),
        added=_marks(drawn & (away_from_ink > tolerance_px), tolerance_px, cap),
    )


def _mask(shapes: Sequence[Shape], width: int, height: int) -> Mask:
    """The shapes filled in, or drawn as 1 px lines when stroked; one call per outline,
    so overlaps stay filled (not even-odd)."""
    canvas = np.zeros((height, width), dtype=np.uint8)
    for s in shapes:
        points = [np.round(np.array(s.polygon)).astype(np.int32)]
        if s.stroke:
            cv2.polylines(canvas, points, isClosed=False, color=1, thickness=1)
        else:
            cv2.fillPoly(canvas, points, 1)
    return canvas.astype(bool)


def _distance(mask: Mask) -> np.ndarray:
    """Distance from every pixel to the nearest mask pixel; infinite when the mask is empty."""
    if not mask.any():
        return np.full(mask.shape, np.inf)
    return cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)


def _near_share(source: Mask, away: np.ndarray, tolerance_px: float) -> float:
    """Share of `source` within the tolerance of the mask `away` measures from; 1.0 when
    `source` is empty: nothing was left out and nothing was added."""
    count = int(source.sum())
    return int((away[source] <= tolerance_px).sum()) / count if count else 1.0


def _covered_by(ink: Mask, ink_px: int, part: Mask, tolerance_px: float) -> float:
    if ink_px == 0 or not part.any():
        return 0.0
    return int((_distance(part)[ink] <= tolerance_px).sum()) / ink_px


def _marks(pixels: Mask, tolerance_px: float, cap: int) -> tuple[Mark, ...]:
    """The largest patches of `pixels`, each outlined with the tolerance round it."""
    if not pixels.any():
        return ()
    grow = round(tolerance_px)
    kernel = np.ones((2 * grow + 1, 2 * grow + 1), np.uint8)
    halo = cv2.dilate(pixels.astype(np.uint8), kernel)
    count, found = cv2.connectedComponents(halo, connectivity=8)
    labels: np.ndarray = np.asarray(found, dtype=np.int32)
    # Each patch's own pixels, not its halo.
    sizes = np.bincount(labels[pixels].astype(np.int64), minlength=count)
    marks = []
    for label in sorted(range(1, count), key=lambda i: -int(sizes[i]))[:cap]:
        contours, _ = cv2.findContours(
            (labels == label).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        outline = cv2.approxPolyDP(max(contours, key=cv2.contourArea), 1.0, True)
        polygon = tuple((float(p[0][0]), float(p[0][1])) for p in outline)
        marks.append(Mark(polygon, int(sizes[label])))
    return tuple(marks)
