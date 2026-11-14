"""A page image as a line network for room tracing (D-024).

Two sources, both from the page's ink:
- stroke centre lines (skeleton -> polylines): walls drawn as lines, door swings,
  fixtures; text and dashes are removed first;
- the outlines of wall bands, closed over their hatching: hatched walls give a mesh of
  short strokes with gaps, but their band edge is continuous.
"""

from collections.abc import Sequence

import cv2
import numpy as np
from shapely.geometry import LineString
from skimage.morphology import skeletonize

from app.ingest.rooms import Gray

INK_BELOW = 215  # CAD plots draw secondary lines in light grey; paper is ~255
BAND_CLOSE_PX = 5  # seals hatching so a hatched wall is one solid band
DASH_PX = 30  # stroke pieces smaller than this both ways are dashes or specks


def page_lines(gray: Gray, words: Sequence[tuple[str, Sequence[float]]]) -> list[LineString]:
    """All lines of the page that can bound a room. `words` are OCR (text, box)."""
    ink = np.where(gray < INK_BELOW, 255, 0).astype(np.uint8)
    bands = wall_band_outlines(ink)  # from untouched ink: a word box never cuts a wall
    strokes = ink.copy()
    for text, (x0, y0, x1, y1) in words:
        if looks_like_text(text):  # junk "words" read from hatching keep their ink
            strokes[max(0, int(y0) - 2) : int(y1) + 2, max(0, int(x0) - 2) : int(x1) + 2] = 0
    strokes = drop_short_pieces(strokes, DASH_PX)
    return centre_lines(strokes) + bands


def wall_band_outlines(ink: np.ndarray, close_px: int = BAND_CLOSE_PX) -> list[LineString]:
    band = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((close_px, close_px), np.uint8))
    band = cv2.morphologyEx(band, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(band, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in contours:
        pts = cv2.approxPolyDP(c, 1.0, True).reshape(-1, 2).astype(float)
        if len(pts) >= 3:
            out.append(LineString([*pts, pts[0]]))
    return out


def centre_lines(ink: np.ndarray, epsilon: float = 1.2) -> list[LineString]:
    """Polylines along the middle of every stroke; curves stay curves."""
    skeleton = skeletonize(ink > 0).astype(np.uint8)
    contours, _ = cv2.findContours(skeleton, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in contours:
        pts = cv2.approxPolyDP(c, epsilon, False).reshape(-1, 2).astype(float)
        if len(pts) >= 2:
            out.append(LineString(pts))
    return out


def drop_short_pieces(strokes: np.ndarray, max_side_px: int) -> np.ndarray:
    """Remove stroke pieces smaller than `max_side_px` both ways: the dashes of a
    dash-dot boundary line, dots and specks. Walls come from the bands anyway."""
    _, labels, stats, _ = cv2.connectedComponentsWithStats(
        (strokes > 0).astype(np.uint8), connectivity=8
    )
    small = (stats[:, cv2.CC_STAT_WIDTH] < max_side_px) & (
        stats[:, cv2.CC_STAT_HEIGHT] < max_side_px
    )
    small[0] = False  # background
    out = strokes.copy()
    out[small[labels]] = 0
    return out


def looks_like_text(text: str) -> bool:
    """At least two letters or digits, and mostly letters/digits: not hatching noise."""
    core = [c for c in text if c.isalnum()]
    return len(core) >= 2 and len(core) >= 0.6 * len(text)
