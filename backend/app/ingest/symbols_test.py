import numpy as np
import pytest

from app.ingest.symbols import find_windows, window_carve

W, H = 200, 120
MIN_PX = 12  # the shortest window in these tests


def _page() -> np.ndarray:
    return np.zeros((H, W), dtype=bool)


def _frame(mask: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> None:
    """A 1 px rectangle outline, edges included."""
    mask[y0, x0 : x1 + 1] = mask[y1, x0 : x1 + 1] = True
    mask[y0 : y1 + 1, x0] = mask[y0 : y1 + 1, x1] = True


def _wall_line(symbols: np.ndarray) -> np.ndarray:
    """A thin wall along y = 50 from x 10 to 150, drawn in the symbols and as a traced wall."""
    symbols[50, 10:151] = True
    walls = _page()
    walls[50, 10:151] = True
    return walls


def test_a_glazing_frame_beside_a_wall_is_a_window() -> None:
    symbols = _page()
    walls = _wall_line(symbols)
    _frame(symbols, 40, 44, 69, 48)  # 30 x 5 px, its glass rows 45..47 inside
    (window,) = find_windows(symbols, _page(), walls, MIN_PX)
    # The frame's ends, on the wall's centre line (y 50); as thick as the frame.
    assert window.a == pytest.approx((40, 50)) and window.b == pytest.approx((69, 50))
    assert window.thickness_px == 5
    assert window.box == (40, 44, 69, 48)


def test_a_window_of_two_panes_is_one_window() -> None:
    symbols = _page()
    walls = _wall_line(symbols)
    _frame(symbols, 40, 44, 69, 48)
    symbols[44:49, 55] = True  # a mullion: panes x 41..54 and 56..68
    (window,) = find_windows(symbols, _page(), walls, MIN_PX)
    assert window.a == pytest.approx((40, 50)) and window.b == pytest.approx((69, 50))


def test_an_upright_window_beside_an_upright_wall() -> None:
    symbols = np.zeros((H, W), dtype=bool)
    symbols[10:110, 100] = True  # wall x = 100
    walls = _page()
    walls[10:110, 100] = True
    _frame(symbols, 102, 30, 106, 59)  # 5 x 30 px, right of the wall
    (window,) = find_windows(symbols, _page(), walls, MIN_PX)
    assert window.a == pytest.approx((100, 30)) and window.b == pytest.approx((100, 59))


def test_a_frame_away_from_any_wall_is_not_a_window() -> None:
    symbols = _page()
    walls = _wall_line(symbols)
    _frame(symbols, 40, 30, 69, 34)  # 15 px above the wall: a shelf or a counter
    assert find_windows(symbols, _page(), walls, MIN_PX) == []


def test_lines_blocks_and_squares_are_not_windows() -> None:
    symbols = _page()
    walls = _wall_line(symbols)
    symbols[46, 40:70] = True  # a 30 x 1 line: no glass inside
    symbols[40:45, 80:85] = True  # a solid 5 x 5 block
    _frame(symbols, 100, 36, 113, 48)  # a square 14 x 13 frame: not a strip
    _frame(symbols, 120, 46, 127, 48)  # a strip 8 px long: shorter than MIN_PX
    assert find_windows(symbols, _page(), walls, MIN_PX) == []


def test_a_strip_with_room_fill_on_both_sides_is_indoors() -> None:
    symbols = _page()
    walls = _wall_line(symbols)
    _frame(symbols, 40, 44, 69, 48)
    fills = np.ones((H, W), dtype=bool)  # filled everywhere: no outside beside the strip
    assert find_windows(symbols, fills, walls, MIN_PX) == []
    fills[:44] = False  # paper above the strip: the outside
    assert len(find_windows(symbols, fills, walls, MIN_PX)) == 1


def test_the_carve_is_the_glass_and_its_frame_but_not_the_wall() -> None:
    symbols = _page()
    walls = _wall_line(symbols)
    _frame(symbols, 40, 44, 69, 48)
    carve = window_carve(find_windows(symbols, _page(), walls, MIN_PX), (H, W))
    assert carve[44:49, 40:70].all()  # the frame box, 30 x 5
    assert not carve[50].any()  # the wall line is kept
    assert carve.sum() == 30 * 5


def test_a_frame_drawn_on_the_wall_line_keeps_the_line() -> None:
    symbols = _page()
    walls = _wall_line(symbols)
    _frame(symbols, 40, 46, 69, 50)  # its outer line is the wall line, y 50
    (window,) = find_windows(symbols, _page(), walls, MIN_PX)
    # The wall line is the row that runs on past both ends: y 50, not the frame's middle 48.
    assert window.a == pytest.approx((40, 50)) and window.b == pytest.approx((69, 50))
    carve = window_carve([window], (H, W))
    # Rows 46..48 go; 49..51 (the line and KEEP_PX = 1 either side) stay.
    assert carve[46:49, 40:70].all() and carve.sum() == 30 * 3
