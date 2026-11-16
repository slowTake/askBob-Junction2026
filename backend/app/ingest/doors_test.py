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
