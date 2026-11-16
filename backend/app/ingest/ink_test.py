import numpy as np
from PIL import Image

from app.ingest.ink import separate_colours
from app.ingest.line_trace import INK_BELOW
from app.ingest.rooms import ink_mask

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
# Greys by hand, 0.299 R + 0.587 G + 0.114 B rounded:
YELLOW = (240, 240, 144)  # colorful-34's room fill: 229
BLUE = (176, 208, 240)  # colorful-34's sloped-ceiling zone: 202
RED = (220, 40, 40)  # a red height label: 94
INK_ON_YELLOW = (120, 120, 72)  # a black line half covering the yellow fill: 115


def _page(width: int = 10, height: int = 10) -> np.ndarray:
    return np.full((height, width, 3), WHITE, np.uint8)


def _grey(rgb: np.ndarray) -> np.ndarray:
    """The grey page raster ingest used before colours were separated."""
    return np.asarray(Image.fromarray(rgb).convert("L"), dtype=np.uint8)


def test_a_grey_scan_is_left_as_it_is() -> None:
    page = _page()
    page[2, :] = BLACK  # a wall line
    page[5, 1:4] = (128, 128, 128)  # a grey line
    page[7, 7] = (200, 210, 190)  # scanner tint on paper: chroma 20, below the cut of 24
    layers = separate_colours(page)
    assert not layers.fills.any() and not layers.annotations.any()
    assert np.array_equal(layers.ink_page, _grey(page))
    assert np.array_equal(layers.ocr_page, _grey(page))
    assert np.array_equal(layers.ink, ink_mask(_grey(page)))


def test_fills_annotations_and_ink_are_told_apart() -> None:
    page = _page()
    page[0:4, 0:5] = YELLOW  # 4 x 5 = 20 px of fill
    page[1, 1:3] = INK_ON_YELLOW  # 2 of them are a black line on the fill: 18 fill left
    page[6:8, 0:3] = RED  # 2 x 3 = 6 px of red label
    page[9, :] = BLACK  # 10 px of wall line
    layers = separate_colours(page)
    assert layers.fills.sum() == 18
    assert layers.annotations.sum() == 6
    assert layers.annotations[6:8, 0:3].all()
    # Ink: the 10 px wall line and the 2 px line on the fill; Otsu splits the ink page's
    # grey levels {0, 115, 255} between 115 and 255, so both are ink and nothing else is.
    assert layers.ink.sum() == 12
    assert layers.ink[9, :].all() and layers.ink[1, 1:3].all()


def test_the_ink_page_keeps_only_the_line_work() -> None:
    page = _page()
    page[0:4, 0:5] = YELLOW
    page[1, 1:3] = INK_ON_YELLOW
    page[6:8, 0:3] = RED
    layers = separate_colours(page)
    assert (layers.ink_page[0:4, 0:5][~layers.ink[0:4, 0:5]] == 255).all()  # fill is paper
    assert (layers.ink_page[6:8, 0:3] == 255).all()  # red labels are not walls
    assert (layers.ink_page[1, 1:3] == 115).all()  # the line keeps its grey


def test_the_ocr_page_reads_lines_and_labels_on_a_fill_as_on_paper() -> None:
    page = _page()
    page[0:4, 0:5] = YELLOW
    page[1, 1:3] = INK_ON_YELLOW
    page[6:8, 0:3] = RED
    layers = separate_colours(page)
    # Each pixel is divided by the fill colour around it (the window covers this small page):
    # yellow / yellow and paper / yellow are white.
    assert (layers.ocr_page[0:4, 0:5][~layers.ink[0:4, 0:5]] == 255).all()
    # The half-covering line: (120, 120, 72) / (240, 240, 144) * 255 = 127.5 each, rounded
    # to 128: half grey, as it would be on paper.
    assert (layers.ocr_page[1, 1:3] == 128).all()
    # Red: (220, 40, 40) / (240, 240, 144) * 255 = (233.75, 42.5, 70.8) -> (234, 42, 71),
    # grey 0.299 * 234 + 0.587 * 42 + 0.114 * 71 = 103: kept for OCR, unlike on the ink page.
    assert (layers.ocr_page[6:8, 0:3] == 103).all()


def test_the_ocr_page_is_untouched_away_from_fills() -> None:
    page = _page(40, 10)
    page[0:10, 0:4] = YELLOW  # a fill at the left edge
    page[5, 30:40] = (
        RED  # a label from x 30: 26 px past the fill, beyond the 15 px window's reach of 7
    )
    layers = separate_colours(page)
    assert (layers.ocr_page[5, 30:40] == 94).all()  # its plain grey (hand: 94)


def test_a_blue_zone_is_no_longer_dark_enough_to_be_a_line() -> None:
    page = _page()
    page[0:5, :] = BLUE  # grey 203: below line tracing's INK_BELOW of 215 until now
    assert (_grey(page)[0:5, :] < INK_BELOW).all()
    layers = separate_colours(page)
    assert layers.fills.sum() == 50  # 5 rows x 10 columns
    assert (layers.ink_page >= INK_BELOW).all()


def test_dark_coloured_pen_is_ink() -> None:
    page = _page()
    page[4, :] = (30, 30, 200)  # blue pen: grey 49, not red, so it is line work
    layers = separate_colours(page)
    assert not layers.fills.any() and not layers.annotations.any()
    assert layers.ink.sum() == 10
