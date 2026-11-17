import cv2
import numpy as np
import pytest

from app.domain.polygons import point_in_polygon
from app.ingest.doors import Door
from app.ingest.page_symbols import (
    PageSymbols,
    beyond_symbols,
    symbol_elements,
    trace_with_symbols,
)
from app.ingest.types import ExtractedElement

H, W = 120, 200
RUN = 20


def _window_on_a_band() -> np.ndarray:
    ink = np.zeros((H, W), dtype=bool)
    ink[50:56, 10:150] = True  # a band 6 px thick, rows 50..55
    # A window frame 2 rows above it: rows 44..47, x 40..69, glass rows 45..46.
    ink[44, 40:70] = ink[47, 40:70] = True
    ink[44:48, 40] = ink[44:48, 69] = True
    return ink


def test_a_window_on_a_wall_is_found_and_not_traced_as_wall() -> None:
    ink = _window_on_a_band()
    found = trace_with_symbols(ink, ink, np.zeros_like(ink), RUN)
    (window,) = found.windows
    # On the band's centre line: rows 50..55 run on past both ends, their middle is 52.5.
    assert window.a == pytest.approx((40, 52.5)) and window.b == pytest.approx((69, 52.5))
    (wall,) = found.walls
    assert not point_in_polygon((55, 45.5), wall.polygon)  # the frame is not wall
    assert point_in_polygon((55, 52.5), wall.polygon)  # the wall runs on under the window


def test_without_a_window_the_walls_are_traced_once_as_before() -> None:
    ink = np.zeros((H, W), dtype=bool)
    ink[50:56, 10:150] = True
    found = trace_with_symbols(ink, ink, np.zeros_like(ink), RUN)
    assert found.windows == [] and len(found.walls) == 1


def test_a_window_is_stored_with_its_gap_and_frame() -> None:
    ink = _window_on_a_band()
    found = trace_with_symbols(ink, ink, np.zeros_like(ink), RUN)
    (el,) = symbol_elements(found, scale_mm=10.0, page_height=H)
    assert el.kind == "window" and el.source == "derived"
    assert el.bbox == (40, 44, 69, 47)
    assert el.properties["opening"] == {"a": [40, 52.5], "b": [69, 52.5]}
    assert el.properties["polygon_px"] == [[40, 44], [69, 44], [69, 47], [40, 47]]
    assert el.value_mm == 290  # 29 px between the ends x 10 mm


def test_a_door_is_stored_with_its_gap_hinge_and_swing() -> None:
    # Hinge (80, 50), closing at (100, 50) on the wall, leaf drawn open to (80, 70).
    door = Door(a=(80, 50), b=(100, 50), toward=(90, 60), leaf=(80, 70), radius_px=20)
    (el,) = symbol_elements(PageSymbols([], [], [door]), scale_mm=None, page_height=H)
    assert el.kind == "door"
    assert el.properties["opening"] == {"a": [80, 50], "b": [100, 50]}
    assert el.properties["hinge"] == "a" and el.properties["toward"] == [90, 60]
    assert el.properties["radius_px"] == 20
    assert el.properties["polygon_px"] == [[80, 50], [100, 50], [80, 70]]
    # The box round the leaf and its swing: the quarter square from the hinge.
    assert el.bbox == (80, 50, 100, 70)
    assert el.value_mm is None  # no scale


def test_the_models_doors_and_windows_give_way_to_the_drawn_ones() -> None:
    drawn = [ExtractedElement(kind="door", source="derived", bbox=(80, 50, 100, 70))]
    near = ExtractedElement(kind="door", source="vision", bbox=(82, 52, 100, 72))  # 2.8 px
    far = ExtractedElement(kind="window", source="vision", bbox=(10, 10, 30, 14))
    fixture = ExtractedElement(kind="fixture", source="vision", bbox=(80, 50, 100, 70))
    assert beyond_symbols([near, far, fixture], drawn, reach_px=4) == [far, fixture]


def test_a_fixture_s_ring_is_carved_out_of_the_walls_and_stored_as_its_outline() -> None:
    ink = np.zeros((H, W), np.uint8)
    ink[50:56, 10:190] = 1  # a band 6 px thick, rows 50..55
    # A chair on it: a 14 x 14 outline (x 80..93, y 56..69) and its inner square 2 px in.
    # The page's longest side is 200: a fixture's hole is at most 0.045 x 200 = 9 px across;
    # the inner square's hole is x 83..90 (8 px).
    cv2.rectangle(ink, (80, 56), (93, 69), 1, 1)
    cv2.rectangle(ink, (82, 58), (91, 67), 1, 1)
    mask = ink.astype(bool)
    # No symbol layer: a door could read in the square (a leaf and its quarter) and take
    # the hole for its swing.
    found = trace_with_symbols(mask, np.zeros_like(mask), np.zeros_like(mask), RUN)
    assert len(found.fixtures) == 1
    assert not any(point_in_polygon((80, 62), w.polygon) for w in found.walls)  # not wall
    assert any(point_in_polygon((150, 52.5), w.polygon) for w in found.walls)  # the band is
    (el,) = [e for e in symbol_elements(found, scale_mm=10.0, page_height=H) if e.kind == "fixture"]
    assert el.source == "derived" and el.label is None
    assert el.properties["drawn"] == "ring"
    xs = [p[0] for p in el.properties["polygon_px"]]
    ys = [p[1] for p in el.properties["polygon_px"]]
    # The outline is the chair's outer square, x 80..93, y 56..69 (1 px simplification).
    assert (min(xs), min(ys), max(xs), max(ys)) == pytest.approx((80, 56, 93, 69), abs=1)
    assert el.bbox == (min(xs), min(ys), max(xs), max(ys))
    assert el.footprint_mm is not None  # the scale is known


def test_the_models_fixtures_give_way_to_the_drawn_ones() -> None:
    drawn = [ExtractedElement(kind="fixture", source="derived", bbox=(80, 50, 100, 70))]
    near = ExtractedElement(kind="fixture", source="vision", bbox=(82, 52, 100, 72))  # 2.8 px
    door = ExtractedElement(kind="door", source="vision", bbox=(80, 50, 100, 70))
    assert beyond_symbols([near, door], drawn, reach_px=4) == [door]
