import cv2
import numpy as np
from shapely.geometry import Polygon

from app.domain.room_faces import room_outlines
from app.ingest.line_trace import drop_short_pieces, page_lines, wall_band_outlines


def _rooms(img: np.ndarray, labels: list[tuple[float, float]], min_area: float) -> list:
    return room_outlines(page_lines(img, words=[]), labels, min_area_px=min_area, min_width_px=6)


def test_a_door_swing_closes_the_doorway() -> None:
    """Two rooms with a 20 px doorway in the wall at x=60 (y 15..35). The door leaf
    (hinge at (60, 15), 20 px long) and its quarter arc span the gap, so the drawing's
    own lines keep the rooms apart: each label gets its own room."""
    img = np.full((70, 120), 255, np.uint8)
    cv2.rectangle(img, (5, 5), (110, 60), 0, 2)
    cv2.line(img, (60, 5), (60, 15), 0, 2)
    cv2.line(img, (60, 35), (60, 60), 0, 2)
    cv2.line(img, (60, 15), (80, 15), 0, 1)  # leaf, open into the right room
    cv2.ellipse(img, (60, 15), (20, 20), 0, 0, 90, 0, 1)  # swing to the far jamb
    left, right = _rooms(img, [(30, 30), (95, 45)], min_area=300)
    assert left is not None and right is not None and left != right


def test_dashed_lines_are_not_walls() -> None:
    # A room 100 x 60 crossed by a dashed line (8 px dashes, 8 px gaps): one room.
    img = np.full((80, 130), 255, np.uint8)
    cv2.rectangle(img, (10, 10), (110, 70), 0, 3)
    for y in range(12, 70, 16):
        cv2.line(img, (60, y), (60, y + 8), 0, 1)
    [room] = _rooms(img, [(30, 40)], min_area=500)
    # The inside of the walls is about 96 x 56 = 5376 px²; cut at the dashes it would
    # be about half. (Two labels in one room would give neither: that is a merge.)
    assert room is not None and Polygon(room).area > 4500


def test_drop_short_pieces_keeps_long_strokes() -> None:
    ink = np.zeros((50, 100), np.uint8)
    ink[10, 5:95] = 255  # a 90 px line: kept
    ink[30, 5:15] = 255  # a 10 px dash: dropped
    out = drop_short_pieces(ink, max_side_px=30)
    assert out[10].sum() == 90 * 255 and out[30].sum() == 0


def test_hatched_wall_band_has_one_continuous_outline() -> None:
    # A 10 px wall band drawn only as diagonal hatching: closing seals it, so its
    # outline is one ring around the band (two edges joined at the ends).
    ink = np.zeros((40, 120), np.uint8)
    for x in range(10, 110, 4):
        cv2.line(ink, (x, 25), (x + 6, 15), 255, 1)
    outlines = wall_band_outlines(ink)
    assert len(outlines) == 1
    xs = [p[0] for p in outlines[0].coords]
    # hatch strokes run x 10..112; the 3 px opening trims a pixel off each end
    assert min(xs) <= 11 and max(xs) >= 110


def test_text_is_not_traced_but_hatching_noise_is_kept() -> None:
    # A word box over a wall must not cut the wall: junk "words" read from hatching
    # (no letters/digits) are not erased.
    img = np.full((60, 120), 255, np.uint8)
    cv2.rectangle(img, (5, 5), (110, 50), 0, 3)
    cv2.putText(img, "Bad", (40, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1)
    words = [("Bad", (38, 20, 70, 34)), ("///", (0, 3, 120, 8))]
    [room] = room_outlines(page_lines(img, words), [(20, 25)], min_area_px=500, min_width_px=6)
    assert room is not None  # the top wall (under the junk box) still closes the room
