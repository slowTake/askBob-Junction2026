"""Find the drawing on a sheet and decide how much to enlarge it (D-022)."""

import cv2
import numpy as np

CLOSE_PX = 5  # seals hatching inside walls so a hatched wall reads as one solid stroke
SHEET_SCALE = 1.5  # best of 0.75 / 1 / 1.5 on a Swiss sheet (D-022)


def _ink(gray: np.ndarray) -> np.ndarray:
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return ink


def thick_ink(gray: np.ndarray) -> np.ndarray:
    """Ink that survives closing and a 3x3 opening: walls, not thin lines or text."""
    ink = cv2.morphologyEx(_ink(gray), cv2.MORPH_CLOSE, np.ones((CLOSE_PX, CLOSE_PX), np.uint8))
    return cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))


def has_frame(gray: np.ndarray) -> bool:
    """A sheet: some ink line (frame, title-block rule) spans nearly the whole page."""
    if gray.min() == gray.max():
        return False
    count, _, stats, _ = cv2.connectedComponentsWithStats(_ink(gray))
    h, w = gray.shape
    return any(
        stats[i, cv2.CC_STAT_WIDTH] >= 0.9 * w and stats[i, cv2.CC_STAT_HEIGHT] >= 0.9 * h
        for i in range(1, count)
    )


def scale_for(framed: bool) -> float:
    return SHEET_SCALE if framed else 1.0


def drawing_box(gray: np.ndarray, margin: int = 20) -> tuple[int, int, int, int]:
    """(x0, y0, x1, y1) of the drawing on a framed sheet; the whole image otherwise.

    Grows from the biggest wall structure, adding pieces within a fixed distance of it,
    so the scale bar, north arrow and legend (which sit apart) stay out.
    """
    h, w = gray.shape
    whole = (0, 0, w, h)
    if not has_frame(gray):
        return whole
    count, _, stats, _ = cv2.connectedComponentsWithStats(thick_ink(gray))
    inner = [
        i for i in range(1, count)
        if stats[i, cv2.CC_STAT_WIDTH] < 0.85 * w and stats[i, cv2.CC_STAT_HEIGHT] < 0.85 * h
    ]  # fmt: skip
    if not inner:
        return whole
    best = max(inner, key=lambda i: stats[i, cv2.CC_STAT_AREA])
    x0, y0 = int(stats[best, 0]), int(stats[best, 1])
    x1, y1 = x0 + int(stats[best, 2]), y0 + int(stats[best, 3])
    pad = 0.15 * max(x1 - x0, y1 - y0)  # fixed: a growing pad would swallow the legend
    joined = {best}
    grew = True
    while grew:
        grew = False
        for i in inner:
            if i in joined:
                continue
            bx0, by0 = int(stats[i, 0]), int(stats[i, 1])
            bx1, by1 = bx0 + int(stats[i, 2]), by0 + int(stats[i, 3])
            if bx0 <= x1 + pad and bx1 >= x0 - pad and by0 <= y1 + pad and by1 >= y0 - pad:
                joined.add(i)
                x0, y0, x1, y1 = min(x0, bx0), min(y0, by0), max(x1, bx1), max(y1, by1)
                grew = True
    return max(0, x0 - margin), max(0, y0 - margin), min(w, x1 + margin), min(h, y1 + margin)
