"""Measure dimension lines on a rendered page, to fit its scale from printed dimensions.

A dimension label sits beside its dimension line, centred between two ticks: the
extension lines, slashes or dots that cross the line where the measured length starts
and ends. Its length in pixels together with the printed value gives the scale.
"""

import math

import numpy as np

from app.domain.geometry import BBox
from app.domain.scale_fit import consensus_scale, scale_from_dimension
from app.ingest.rooms import Mask

LINE_COVERAGE = 0.9  # share of the label's width the line must run under
MAX_GAP_PX = 2  # breaks a scanned line may have before it counts as ended
SEARCH_HEIGHTS = 1.5  # how far from the label to look for its line, in label heights
TICK_HEIGHTS = 0.6  # how far a tick reaches across the line, in label heights


def fit_dimension_scale(
    ink: Mask, dimensions: list[tuple[float, BBox]], erase: list[BBox] | None = None
) -> tuple[float, int] | None:
    """(mm per pixel, number of agreeing labels) from (value in mm, label box) pairs.

    `erase` are text boxes that must not be mistaken for ticks; defaults to the labels.
    """
    boxes = erase if erase is not None else [box for _, box in dimensions]
    estimates: list[float] = []
    for value_mm, box in dimensions:
        span = dimension_span(ink, box, boxes)
        scale = scale_from_dimension(value_mm, span) if span else None
        if scale:
            estimates.append(scale)
    return consensus_scale(estimates)


def dimension_span(ink: Mask, label: BBox, erase: list[BBox]) -> float | None:
    """Pixel length of the dimension line segment that `label` annotates, or None.

    Labels taller than wide are vertical text: measured on the transposed page.
    """
    x0, y0, x1, y1 = label
    if y1 - y0 > x1 - x0:
        return dimension_span(ink.T, (y0, x0, y1, x1), [(b[1], b[0], b[3], b[2]) for b in erase])
    height = y1 - y0
    if height <= 0:
        return None
    marks = ink.copy()  # ink without text, so letters never look like ticks
    for bx0, by0, bx1, by1 in erase:
        marks[int(by0) : math.ceil(by1), int(bx0) : math.ceil(bx1)] = False
    # Search without text: the label's own bottom strokes would pass for a line under it.
    row = _line_row(marks, label, round(SEARCH_HEIGHTS * height))
    if row is None:
        return None
    reach = max(4, round(TICK_HEIGHTS * height))
    start = int((x0 + x1) / 2)
    left = _walk_to_tick(ink, marks, row, start, -1, reach)
    right = _walk_to_tick(ink, marks, row, start, 1, reach)
    if left is None or right is None:
        return None
    return right - left


def _line_row(ink: Mask, label: BBox, search: int) -> int | None:
    """The row of the straight line running under (or over) the whole label, nearest first."""
    x0, y0, x1, y1 = label
    c0, c1 = int(x0), math.ceil(x1)
    top, bottom = int(y0), math.ceil(y1)
    rows = ink.shape[0]

    def coverage(r: int, band: int) -> float:
        lo, hi = max(0, r - band), min(rows, r + band + 1)
        return float(ink[lo:hi, c0:c1].any(axis=0).mean())

    for d in range(max(1, search)):
        for r in (bottom + d, top - 1 - d):
            if 1 <= r < rows - 1 and c1 > c0 and coverage(r, 1) >= LINE_COVERAGE:
                # A slightly tilted scan spreads the line over two rows; take the fuller one.
                return max((r - 1, r, r + 1), key=lambda rr: coverage(rr, 0))
    return None


def _walk_to_tick(
    ink: Mask, marks: Mask, row: int, start: int, step: int, reach: int
) -> float | None:
    """Follow the line from `start` until a tick crosses it; the tick's x, or None."""
    cols = ink.shape[1]
    line = ink[max(0, row - 1) : row + 2].any(axis=0)
    half = max(2, reach // 2)
    gap = 0
    c = start
    while 0 <= c < cols:
        gap = 0 if line[c] else gap + 1
        if gap > MAX_GAP_PX:
            return None  # the line ended without a tick
        lo, hi = max(0, c - half), c + half + 1
        above = marks[max(0, row - reach) : max(0, row - 1), lo:hi]
        below = marks[row + 2 : row + reach + 1, lo:hi]
        if above.any() and below.any():
            return _tick_centre(marks, row, c, reach)
        c += step
    return None


def _tick_centre(marks: Mask, row: int, c: int, reach: int) -> float:
    """Ticks are symmetric about the point where they cross the line: average the x of
    the ink above the line with the x of the ink below it, near the detected column."""
    lo = max(0, c - 2 * reach)
    window = slice(lo, c + 2 * reach + 1)
    above = marks[max(0, row - reach) : max(0, row - 1), window]
    below = marks[row + 2 : row + reach + 1, window]
    return (_mean_x(above) + _mean_x(below)) / 2 + lo


def _mean_x(region: Mask) -> float:
    xs = np.nonzero(region)[1]
    return float(xs.mean())
