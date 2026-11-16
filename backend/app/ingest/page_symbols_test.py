import numpy as np
import pytest

from app.domain.polygons import point_in_polygon
from app.ingest.page_symbols import symbol_elements, trace_with_symbols

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
