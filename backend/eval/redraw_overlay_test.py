from pathlib import Path

import numpy as np
import pytest

from eval.redraw_overlay import DOOR, _image_beside, draw_overlay
from eval.redraw_sheet import Opening, Sheet, Wall, band


def _grey(width: int, height: int, value: int = 100) -> np.ndarray:
    return np.full((height, width, 3), value, dtype=np.uint8)


def test_the_output_is_the_input_enlarged_by_the_scale() -> None:
    out = draw_overlay(_grey(40, 30), Sheet(), 3)
    assert out.shape == (90, 120, 3)  # 30 * 3 rows, 40 * 3 columns
    assert out.dtype == np.uint8


def test_an_empty_sheet_returns_the_enlarged_image_unchanged() -> None:
    photo = np.array([[[10, 20, 30], [40, 50, 60]], [[70, 80, 90], [1, 2, 3]]], dtype=np.uint8)
    out = draw_overlay(photo, Sheet(), 3)
    # Each source pixel becomes a 3 x 3 block of itself (nearest).
    assert (out[0:3, 0:3] == [10, 20, 30]).all()
    assert (out[0:3, 3:6] == [40, 50, 60]).all()
    assert (out[3:6, 0:3] == [70, 80, 90]).all()
    assert (out[3:6, 3:6] == [1, 2, 3]).all()


def test_a_wall_pixel_is_tinted_and_a_pixel_off_the_wall_is_not() -> None:
    # A 2 px band along row 10 from x 2 to 37: wall_mask fills rows 9..11.
    wall = Wall(band((2.0, 10.0), (37.0, 10.0), 2.0))
    out = draw_overlay(_grey(40, 30), Sheet(walls=(wall,)), 2)
    # Source pixel (4, 10) is the 2 x 2 block at rows 20-21, columns 8-9, inside the band and
    # away from its outline and its label (which sits by the middle, x 19.5).
    # Green: 100 * (1 - 0.45) + 0 * 0.45 = 55. Red: 100 * 0.55 + 230 * 0.45 = 158.5, > 100.
    assert out[20, 9, 1] == 55
    assert out[20, 9, 0] > 100
    # Source row 20 is 10 px below the band: untouched grey.
    assert (out[40, 9] == [100, 100, 100]).all()


def test_where_two_walls_overlap_the_overlap_is_tinted_too() -> None:
    # Two 20 x 20 squares overlapping on x, y 10..20. Source pixel (11, 18) lies in both,
    # off their outlines (x, y 10 and 20) and below the first label (from (12, 12), about
    # 4 px tall at scale 1); at scale 1 it is pixel [18, 11]. Green: 100 * 0.55 = 55.
    a = Wall(((0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)))
    b = Wall(((10.0, 10.0), (30.0, 10.0), (30.0, 30.0), (10.0, 30.0)))
    out = draw_overlay(_grey(40, 40), Sheet(walls=(a, b)), 1)
    assert out[18, 11, 1] == 55


def test_a_door_is_drawn_along_its_gap() -> None:
    door = Opening("door", (5.0, 5.0), (15.0, 5.0), hinge=(5.0, 5.0), toward=(5.0, 12.0))
    out = draw_overlay(_grey(30, 20), Sheet(openings=(door,)), 2)
    # The gap runs along enlarged row 5 * 2 + 0.5 = 10.5; x 9 is source 9 -> enlarged 18.5,
    # past the hinge ring (radius 4 around x 10.5) and before the label (from x 23.5).
    column = out[9:13, 18]
    assert any((px == DOOR).all() for px in column)


def test_a_scale_below_one_is_refused() -> None:
    with pytest.raises(ValueError):
        draw_overlay(_grey(4, 4), Sheet(), 0)


def test_the_image_defaults_to_the_png_beside_the_truth_file() -> None:
    truth = Path("eval/redraw_bench/colorful-34.truth.json")
    assert _image_beside(truth) == Path("eval/redraw_bench/colorful-34.png")
