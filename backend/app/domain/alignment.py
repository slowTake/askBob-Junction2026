"""Deterministic registration of matching drawing labels; no image or file I/O."""

import math
from dataclasses import dataclass
from itertools import combinations

from app.domain.geometry import BBox, Point


@dataclass(frozen=True)
class Alignment:
    real: float
    imag: float
    x: float
    y: float
    support: int
    rms_px: float

    @property
    def scale(self) -> float:
        return math.hypot(self.real, self.imag)

    def apply(self, point: Point) -> Point:
        x, y = point
        return (self.real * x - self.imag * y + self.x, self.imag * x + self.real * y + self.y)


def label_anchor(box: BBox, horizontal: int, vertical: int) -> Point:
    """The CAD insertion point corresponding to an OCR text box (DXF alignment codes)."""
    x0, y0, x1, y1 = box
    x = (x0 + x1) / 2 if horizontal in (1, 4) else x1 if horizontal == 2 else x0
    y = (y0 + y1) / 2 if vertical == 2 or horizontal == 4 else y0 if vertical == 3 else y1
    return x, y


def _fit(pairs: list[tuple[Point, Point]]) -> Alignment | None:
    source = [complex(*a) for a, _ in pairs]
    target = [complex(*b) for _, b in pairs]
    sc, tc = sum(source) / len(source), sum(target) / len(target)
    variance = sum(abs(p - sc) ** 2 for p in source)
    if variance <= 1e-9:
        return None
    a = sum((p - sc).conjugate() * (q - tc) for p, q in zip(source, target, strict=True)) / variance
    b = tc - a * sc
    rms = math.sqrt(
        sum(abs(a * p + b - q) ** 2 for p, q in zip(source, target, strict=True)) / len(pairs)
    )
    if not all(math.isfinite(v) for v in (a.real, a.imag, b.real, b.imag, rms)) or abs(a) <= 1e-9:
        return None
    return Alignment(a.real, a.imag, b.real, b.imag, len(pairs), rms)


def align_labels(pairs: list[tuple[Point, Point]], tolerance_px: float = 5.0) -> Alignment | None:
    """Fit uniform scale, rotation and translation, rejecting inconsistent OCR labels.

    Every pair of anchors supplies a hypothesis; the best is refitted on its
    inliers. At least three labels and 75% agreement are required. No random RANSAC.
    """
    if len(pairs) < 3 or tolerance_px <= 0:
        return None
    if not all(math.isfinite(v) for pair in pairs for point in pair for v in point):
        return None
    best: Alignment | None = None
    for sample in combinations(pairs, 2):
        hypothesis = _fit(list(sample))
        if hypothesis is None:
            continue
        inliers = [
            pair for pair in pairs if math.dist(hypothesis.apply(pair[0]), pair[1]) <= tolerance_px
        ]
        if len(inliers) < max(3, math.ceil(0.75 * len(pairs))):
            continue
        fitted = _fit(inliers)
        if (
            fitted
            and fitted.rms_px <= tolerance_px
            and (best is None or (-fitted.support, fitted.rms_px) < (-best.support, best.rms_px))
        ):
            best = fitted
    return best
