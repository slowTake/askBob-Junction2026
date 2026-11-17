import cv2
import numpy as np
import pytest

from app.domain.polygons import point_in_polygon
from app.ingest.doors import Door
from app.ingest.fixtures import Fixtures, find_fixtures, without_swings
from app.ingest.page_symbols import wall_raster
from app.ingest.wall_trace import trace_walls

# A 400 x 400 page: the longest side L = 400, so a fixture's hole is at most
# 0.045 x 400 = 18 px across and 18^2 = 324 px in area.
H = W = 400
RUN = 12  # MIN_RUN_PX: a band component spanning 12 px is a band


def _find(ink: np.ndarray, text: tuple[tuple[float, float, float, float], ...] = ()) -> Fixtures:
    first = trace_walls(ink, RUN, text)
    walls = wall_raster(first, ink.shape)
    lines = wall_raster([w for w in first if w.drawn == "line"], ink.shape)
    return find_fixtures(ink, walls, lines, RUN, text)


def _square(ink: np.ndarray, x0: int, y0: int, side: int) -> None:
    cv2.rectangle(ink, (x0, y0), (x0 + side - 1, y0 + side - 1), 1, 1)


def _chair_on_a_band() -> np.ndarray:
    ink = np.zeros((H, W), np.uint8)
    ink[100:106, 50:351] = 1  # a band 6 px thick, rows 100..105
    ink[106:116, 200:206] = 1  # a short stub of it, 6 x 10 px, below
    _square(ink, 100, 106, 14)  # the chair's outline, x 100..113, y 106..119, on the band
    _square(ink, 102, 108, 10)  # and its inner square 2 px in: x 102..111, y 108..117
    return ink


def _rings(ink: np.ndarray, centre: tuple[int, int]) -> None:
    """Two concentric 1 px circles, r 8 and 10: a WC bowl or a burner."""
    cv2.circle(ink, centre, 8, 1, 1)
    cv2.circle(ink, centre, 10, 1, 1)


def test_a_ring_touching_a_wall_is_a_fixture_and_the_wall_is_unchanged() -> None:
    ink = _chair_on_a_band().astype(bool)
    found = _find(ink)
    (fixture,) = found.fixtures
    # The outline is the chair's outer square: x 100..113, y 106..119 (1 px simplification).
    xs, ys = [p[0] for p in fixture.polygon], [p[1] for p in fixture.polygon]
    assert (min(xs), min(ys), max(xs), max(ys)) == pytest.approx((100, 106, 113, 119), abs=1)
    # The carve is thin ink only: none of the band (rows 100..105) or its stub.
    assert not found.carve[100:106].any() and not found.carve[106:116, 200:206].any()
    # Its rim lies on the band the first trace takes as wall: not closed by itself.
    assert not found.self_closed.any()
    traced = trace_walls(ink, RUN, carve=found.carve)
    band = [w for w in traced if point_in_polygon((200, 102.5), w.polygon)]
    assert len(band) == 1 and band[0].thickness_px == pytest.approx(6, abs=0.5)
    assert any(point_in_polygon((106, 102.5), w.polygon) for w in traced)  # above the chair
    assert any(point_in_polygon((202.5, 112), w.polygon) for w in traced)  # the stub stays
    assert not any(point_in_polygon((100, 112), w.polygon) for w in traced)  # the chair is not


def test_a_double_ring_alone_is_a_fixture_closed_by_itself() -> None:
    ink = np.zeros((H, W), np.uint8)
    _rings(ink, (200, 200))
    found = _find(ink.astype(bool))
    (fixture,) = found.fixtures
    # The outline is the outer circle: 200 +- 10 (1 px simplification).
    xs, ys = [p[0] for p in fixture.polygon], [p[1] for p in fixture.polygon]
    assert (min(xs), min(ys), max(xs), max(ys)) == pytest.approx((190, 190, 210, 210), abs=1)
    # Its rim is on no traced wall (the circles are not straight): all its ink is self-closed,
    # the inner circle (x 192 and 208 on row 200) among it.
    assert (found.self_closed == found.carve).all()
    assert found.self_closed[200, 192] and found.self_closed[200, 208]


def test_a_burner_in_a_counter_is_closed_by_itself() -> None:
    ink = np.zeros((H, W), np.uint8)
    cv2.rectangle(ink, (170, 185), (229, 214), 1, 1)  # the counter, 60 x 30, its sides traced lines
    _rings(ink, (200, 200))
    found = _find(ink.astype(bool))
    assert len(found.fixtures) == 1  # the counter's inside is 58 x 28: over 18 px
    assert found.self_closed[200, 192] and not found.self_closed[185, 200]


def test_a_double_rectangle_over_the_size_is_not_a_fixture() -> None:
    ink = np.zeros((H, W), np.uint8)
    cv2.rectangle(ink, (100, 100), (139, 113), 1, 1)  # 40 x 14
    cv2.rectangle(ink, (102, 102), (137, 111), 1, 1)  # its hole x 103..136: 34 px > 18
    assert _find(ink.astype(bool)).fixtures == []


def test_a_double_line_s_gap_is_a_strip_not_a_fixture() -> None:
    ink = np.zeros((H, W), np.uint8)
    cv2.rectangle(ink, (100, 100), (115, 105), 1, 1)  # hole 14 x 4: 4 <= 6 and 14 >= 2.5 x 4
    assert _find(ink.astype(bool)).fixtures == []


def test_a_hollow_in_a_solid_band_is_a_chimney_not_a_fixture() -> None:
    ink = np.zeros((H, W), np.uint8)
    ink[100:128, 100:128] = 1  # 28 x 28 with walls 6 px thick
    ink[106:122, 106:122] = 0  # the 16 x 16 hole, its rim all thick ink
    assert _find(ink.astype(bool)).fixtures == []


def test_a_closet_between_two_rooms_is_not_a_fixture() -> None:
    ink = np.zeros((H, W), np.uint8)

    def double(x0: int, y0: int, x1: int, y1: int) -> None:  # a 1 px line and another 2 px on
        for d in (0, 2):
            if x0 == x1:
                ink[y0 : y1 + 1, x0 + d] = 1
            else:
                ink[y0 + d, x0 : x1 + 1] = 1

    for x in (10, 52, 68, 110):  # walls of room A | closet | room B
        double(x, 30, x, 74)
    for y in (30, 72):
        double(10, y, 112, y)
    for y in (43, 59):  # the closet's own walls
        double(52, y, 70, y)
    # The closet's hole: x 55..67, y 46..58, 169 px. Rooms A (x 13..51) and B (x 71..109),
    # 39 x 39 = 1,521 px >= 2 x 169, lie 4 px away on either side: two neighbours.
    assert _find(ink.astype(bool)).fixtures == []


def test_a_hatched_band_has_no_fixture_and_keeps_its_thickness() -> None:
    ink = np.zeros((H, W), np.uint8)
    cv2.rectangle(ink, (50, 100), (250, 108), 1, 1)  # 9 px wide outline
    for x in range(53, 250, 3):
        ink[100:109, x] = 1  # hatch lines 3 px apart: cells 2 px wide
    found = _find(ink.astype(bool))
    assert found.fixtures == [] and not found.carve.any()


def test_a_ring_inside_a_word_box_is_text() -> None:
    ink = np.zeros((H, W), np.uint8)
    _rings(ink, (200, 200))
    assert _find(ink.astype(bool), text=((188, 188, 212, 212),)).fixtures == []


def test_a_found_door_s_swing_is_not_a_fixture() -> None:
    ink = np.zeros((H, W), np.uint8)
    _rings(ink, (200, 200))
    found = _find(ink.astype(bool))
    # A door hinged at (190, 190), its quarter disc of radius 25 over x, y 190..215:
    # it covers the ring's hole (200 +- 7) whole.
    door = Door(a=(190, 190), b=(215, 190), toward=(200, 200), leaf=(190, 215), radius_px=25)
    swung = without_swings(found, [door])
    assert swung.fixtures == [] and not swung.carve.any() and not swung.self_closed.any()
    # A door elsewhere leaves it; and an unfound door's swing would be drawn as a fixture.
    far = Door(a=(50, 50), b=(75, 50), toward=(60, 60), leaf=(50, 75), radius_px=25)
    assert len(without_swings(found, [far]).fixtures) == 1
