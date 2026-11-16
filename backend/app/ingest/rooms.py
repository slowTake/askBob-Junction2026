"""Computer-vision helpers on a rendered page: ink mask and room regions.

Baseline heuristics, deliberately simple. Each result carries a low confidence so
the agent knows to double-check it visually (`view_region`).
"""

from typing import Any

import cv2
import numpy as np
import numpy.typing as npt

from app.domain.geometry import BBox, Point

Gray = npt.NDArray[Any]  # uint8 grayscale; OpenCV's stubs return loose dtypes
Mask = npt.NDArray[np.bool_]


def ink_mask(gray: Gray) -> Mask:
    """True where the drawing has ink (Otsu threshold, dark on light)."""
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary > 0


def room_region(
    ink: Mask,
    seed: Point,
    erase: list[BBox],
    max_area_frac: float = 0.25,
    close_px: int = 0,
) -> tuple[list[Point], int] | None:
    """Flood-fill the room around a label. Returns (polygon in px, area in px) or None.

    `erase` removes text boxes from the barrier so labels don't block the fill.
    `close_px` thickens lines to seal small gaps. A fill larger than `max_area_frac`
    of the page leaked through a door opening and is rejected.
    TODO(rooms): close door openings using detected door tags/arcs instead of giving up.
    """
    barrier: Gray = ink.astype(np.uint8) * 255
    for x0, y0, x1, y1 in erase:
        barrier[int(y0) : int(np.ceil(y1)) + 1, int(x0) : int(np.ceil(x1)) + 1] = 0
    if close_px > 0:
        barrier = cv2.dilate(barrier, np.ones((close_px, close_px), np.uint8))
    h, w = barrier.shape
    sx, sy = int(seed[0]), int(seed[1])
    if not (0 <= sx < w and 0 <= sy < h) or barrier[sy, sx]:
        return None
    flood_mask = np.zeros((h + 2, w + 2), np.uint8)
    area, *_ = cv2.floodFill(barrier, flood_mask, (sx, sy), 128)
    if area > max_area_frac * h * w:
        return None
    region = (barrier == 128).astype(np.uint8)
    if region[0, :].any() or region[-1, :].any() or region[:, 0].any() or region[:, -1].any():
        return None  # reached the page edge: leaked out of the building
    contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    outline = max(contours, key=cv2.contourArea)
    approx = cv2.approxPolyDP(outline, 2.0, True)
    polygon = [(float(p[0][0]), float(p[0][1])) for p in approx]
    return polygon, int(area)
