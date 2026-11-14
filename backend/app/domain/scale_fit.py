"""Fit a page's scale from dimensions printed on it, for pages without a known DPI.

Each readable dimension label with a measurable dimension line gives one estimate of
millimetres per pixel. OCR misreads and labels matched to the wrong line give wild
estimates, so a scale is only trusted when several labels agree on it.
"""

from statistics import median

AGREEMENT = 0.03  # estimates within 3% of each other count as the same scale
MIN_SUPPORT = 2  # one label alone is too easy to misread; a wrong scale is worse than none


def scale_from_dimension(value_mm: float, line_px: float) -> float | None:
    """A dimension of `value_mm` drawn as a `line_px` long line: millimetres per pixel."""
    return value_mm / line_px if line_px > 0 else None


def consensus_scale(
    estimates: list[float], tolerance: float = AGREEMENT, min_support: int = MIN_SUPPORT
) -> tuple[float, int] | None:
    """The scale most estimates agree on, as (median of the group, group size).

    Every estimate is tried as the centre of a group of estimates within `tolerance`
    of it; the largest group wins, ties going to the tighter group. Returns None
    when no group reaches `min_support`.
    """
    values = sorted(v for v in estimates if v > 0)
    best: list[float] = []
    for centre in values:
        group = [v for v in values if abs(v - centre) <= tolerance * centre]
        spread = group[-1] - group[0]
        if len(group) > len(best) or (len(group) == len(best) and spread < best[-1] - best[0]):
            best = group
    if len(best) < min_support:
        return None
    return median(best), len(best)
