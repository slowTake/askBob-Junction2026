import math

import cv2
import numpy as np
import pytest

from app.ingest.doors import Door, door_carve, find_doors

H, W = 120, 200


def _wall() -> tuple[np.ndarray, np.ndarray]:
    """A thin wall line along y = 50, x 10..150: in the symbols and as a traced wall."""
    symbols = np.zeros((H, W), np.uint8)
    symbols[50, 10:151] = 1
    walls = np.zeros((H, W), bool)
    walls[50, 10:151] = True
    return symbols, walls


def _door(symbols: np.ndarray, leaf_dy: int, arc_from: int, arc_to: int) -> None:
    """A leaf from the hinge (80, 50) `leaf_dy` px down (or up), and the quarter arc of
    radius 20 round the hinge between the angles given (degrees, y down)."""
    cv2.line(symbols, (80, 50), (80, 50 + leaf_dy), 1, 1)
    cv2.ellipse(symbols, (80, 50), (20, 20), 0, arc_from, arc_to, 1, 1)


def _find(symbols: np.ndarray, walls: np.ndarray) -> list[Door]:
    ink = symbols.astype(bool)
    return find_doors(ink, ink, walls, 7, 25)  # radii 7..25 px


def test_a_leaf_and_quarter_arc_on_a_wall_is_a_door() -> None:
    symbols, walls = _wall()
    _door(symbols, 20, 0, 90)  # leaf to (80, 70); arc from (100, 50) round to (80, 70)
    (door,) = _find(symbols, walls)
    # The gap is hinge to free end on the wall: (80, 50) to (100, 50).
    assert door.a == pytest.approx((80, 50), abs=1.5)
    assert door.b == pytest.approx((100, 50), abs=1.5)
    assert door.radius_px == pytest.approx(20, abs=1)
    assert door.toward[1] > 50  # it opens downwards, the side of the leaf


def test_the_mirrored_door_opens_the_other_way() -> None:
    symbols, walls = _wall()
    _door(symbols, -20, 180, 270)  # leaf up to (80, 30); arc from (60, 50) round to it
    (door,) = _find(symbols, walls)
    assert door.a == pytest.approx((80, 50), abs=1.5)  # the hinge
    assert door.b == pytest.approx((60, 50), abs=1.5)
    assert door.toward[1] < 50


def test_a_circle_by_the_wall_is_not_a_door() -> None:
    symbols, walls = _wall()
    cv2.circle(symbols, (80, 61), 10, 1, 1)  # a stool or a basin, touching the wall at y 51
    assert _find(symbols, walls) == []


def test_a_fan_of_lines_is_not_a_door() -> None:
    symbols, walls = _wall()
    _door(symbols, 20, 0, 90)
    for degrees in range(10, 90, 10):  # 8 radial lines: a stair's winders, not an empty swing
        end = (80 + round(20 * math.cos(math.radians(degrees))),
               50 + round(20 * math.sin(math.radians(degrees))))  # fmt: skip
        cv2.line(symbols, (80, 50), end, 1, 1)
    assert _find(symbols, walls) == []


def test_an_arc_away_from_any_wall_is_not_a_door() -> None:
    symbols, _ = _wall()
    _door(symbols, 20, 0, 90)
    assert _find(symbols, np.zeros((H, W), bool)) == []


def test_the_carve_is_the_leaf_and_arc_but_not_the_gap() -> None:
    symbols, walls = _wall()
    _door(symbols, 20, 0, 90)
    (door,) = _find(symbols, walls)
    carve = door_carve([door], symbols.astype(bool), symbols.astype(bool))
    assert carve[60, 80] and carve[70, 80]  # the leaf
    assert carve[64, 94]  # the arc at 45 degrees: (80 + 14.1, 50 + 14.1)
    assert not carve[50, 90] and not carve[50, 70]  # the wall line through the gap stays


def test_a_page_bigger_than_the_working_size_is_read_shrunk_and_scaled_back() -> None:
    # The first test's door, four times as big (800 x 480 px, over WORK_SIDE_PX = 700):
    # wall y = 200, hinge (320, 200), radius 80, lines 1 px wide.
    symbols = np.zeros((4 * H, 4 * W), np.uint8)
    cv2.line(symbols, (40, 200), (600, 200), 1, 1)
    cv2.line(symbols, (320, 200), (320, 280), 1, 1)
    cv2.ellipse(symbols, (320, 200), (80, 80), 0, 0, 90, 1, 1)
    walls = np.zeros(symbols.shape, bool)
    walls[200, 40:601] = True
    ink = symbols.astype(bool)
    (door,) = find_doors(ink, ink, walls, 28, 100)
    # Read at 700 / 800 of the size, so a pixel there is 8/7 px here: within 4 px.
    assert door.a == pytest.approx((320, 200), abs=4)
    assert door.b == pytest.approx((400, 200), abs=4)
    assert door.radius_px == pytest.approx(80, abs=4)


def test_a_gap_off_the_wall_is_not_a_door() -> None:
    # The wall breaks between x 85 and 95, and the door's gap is x 80..100 on y = 50:
    # within 1 px of the wall are x 80..85 and 95..100, 12 of its 21 px (0.57 < 0.9).
    symbols, walls = _wall()
    symbols[50, 85:96] = 0
    walls[50, 85:96] = False
    _door(symbols, 20, 0, 90)
    assert _find(symbols, walls) == []


def _corner(wall_to_y: int) -> list[Door]:
    """The wall y = 50 and a wall down x = 80 from it to `wall_to_y`, both drawn and
    traced, and the quarter arc of radius 20 round (80, 50) from (100, 50) to (80, 70)
    with no leaf of its own: the wall down x = 80 is where the leaf would be."""
    symbols, walls = _wall()
    symbols[50 : wall_to_y + 1, 80] = 1
    walls[50 : wall_to_y + 1, 80] = True
    cv2.ellipse(symbols, (80, 50), (20, 20), 0, 0, 90, 1, 1)
    return _find(symbols, walls)


def test_a_wall_corner_is_not_a_leaf() -> None:
    # The wall goes on to y = 110: all of the 3..8 px past the leaf's end (y 73..78) is
    # wall, and so is the other reading's (x 103..108 on the wall y = 50).
    assert _corner(110) == []


def test_a_leaf_traced_as_a_short_wall_is_still_a_leaf() -> None:
    # The wall down x = 80 stops at y = 70, the leaf's end: y 73..78 are 3..8 px from any
    # wall (over WALL_NEAR_PX), so the leaf does not run on. The other reading, its leaf
    # on the wall y = 50, runs on past x = 100 and is not a door.
    (door,) = _corner(70)
    assert door.a == pytest.approx((80, 50), abs=1.5)
    assert door.b == pytest.approx((100, 50), abs=1.5)


def test_a_circle_whose_quarter_sits_like_a_door_is_not_a_door() -> None:
    # A circle of radius 20 round (80, 50) on the wall, and a radial line down to
    # (80, 70): each quarter below the wall is a leaf and an arc, but the ring goes on
    # past both ends of it, in all 3 sectors past the leaf and past the free end. Read
    # from a hinge 1 px off the centre, at radius 21, the circle lies up to 1 px off
    # that ring past the free end (20 + sin of the angle): within 2 px, not within 1.5.
    symbols, walls = _wall()
    cv2.circle(symbols, (80, 50), 20, 1, 1)
    cv2.line(symbols, (80, 50), (80, 70), 1, 1)
    assert _find(symbols, walls) == []


def test_two_candidates_4_px_apart_are_one_door() -> None:
    # The standard door and a second reading 4 px along the wall: hinge (84, 50), leaf
    # to (84, 70), its arc from (104, 50). Their boxes, x 80..100 and 84..104 over
    # y 50..70, overlap by 16 x 20 of 20 x 20 = 0.8 > OVERLAP: one door, either hinge.
    symbols, walls = _wall()
    _door(symbols, 20, 0, 90)
    cv2.line(symbols, (84, 50), (84, 70), 1, 1)
    cv2.ellipse(symbols, (84, 50), (20, 20), 0, 0, 90, 1, 1)
    (door,) = _find(symbols, walls)
    assert min(math.dist(door.a, (80, 50)), math.dist(door.a, (84, 50))) <= 1.5
