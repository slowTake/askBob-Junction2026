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
