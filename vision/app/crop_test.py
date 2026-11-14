import cv2
import numpy as np

from app.crop import drawing_box, has_frame, scale_for

W, H = 600, 400


def _sheet(frame: bool) -> np.ndarray:
    """White page; a building drawn as a 6 px wall outline from (100, 80) to (200, 180);
    a thick scale bar far below it; optionally a 1 px frame near the page edge.

    cv2.rectangle with thickness 6 spreads 3 px each side, so the walls' ink spans
    x 97..203 and y 77..183 (by hand).
    """
    page = np.full((H, W), 255, np.uint8)
    cv2.rectangle(page, (100, 80), (200, 180), 0, 6)
    cv2.rectangle(page, (450, 350), (560, 362), 0, -1)  # scale bar: filled, 12 px tall
    if frame:
        cv2.rectangle(page, (5, 5), (W - 6, H - 6), 0, 1)
    return page


def test_a_page_with_a_frame_is_a_sheet() -> None:
    assert has_frame(_sheet(frame=True))
    assert not has_frame(_sheet(frame=False))


def test_sheet_crops_to_the_building_plus_margin() -> None:
    x0, y0, x1, y1 = drawing_box(_sheet(frame=True), margin=20)
    # Wall ink 97..203 x 77..183, plus 20 px margin: about (77, 57, 224, 204); the
    # morphology may move edges by a pixel or two. The scale bar (x >= 450) stays out.
    assert abs(x0 - 77) <= 3 and abs(y0 - 57) <= 3
    assert abs(x1 - 224) <= 3 and abs(y1 - 204) <= 3


def test_an_unframed_image_is_not_cropped() -> None:
    assert drawing_box(_sheet(frame=False)) == (0, 0, W, H)


def test_blank_page_is_not_cropped() -> None:
    assert drawing_box(np.full((H, W), 255, np.uint8)) == (0, 0, W, H)


def test_sheets_are_enlarged_plain_plans_are_not() -> None:
    # D-022: 1.5x scored best on a Swiss sheet; CubiCasa-style plans are read as they are.
    assert scale_for(framed=True) == 1.5
    assert scale_for(framed=False) == 1.0
