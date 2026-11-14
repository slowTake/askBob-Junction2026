import numpy as np
import pytest

from app.domain.tokens import Word
from app.ingest.annotate import annotate_page


def _sheet() -> np.ndarray:
    """200x400 white page: dimension line on row 100 from x = 40 to 360, extension
    lines at x = 50, 150 and 350 (rows 88..112). Segments: 100 px and 200 px."""
    page = np.full((200, 400), 255, np.uint8)
    page[100, 40:361] = 0
    for x in (50, 150, 350):
        page[88:113, x] = 0
    return page


WORDS = [
    Word((85.0, 84.0, 115.0, 96.0), "1000"),  # over 50..150
    Word((235.0, 84.0, 265.0, 96.0), "2000"),  # over 150..350
]


def test_scale_from_dpi_and_scale_note() -> None:
    words = [*WORDS, Word((300.0, 150.0, 340.0, 162.0), "1:50")]
    _, scale, meta = annotate_page(_sheet(), words, "ocr", dpi=150.0)
    # 25.4 / 150 * 50 = 8.4667 mm per pixel; the note wins over the dimensions.
    assert scale == pytest.approx(8.46667, rel=1e-4)
    assert meta["scale_method"] == "dpi"


def test_scale_fitted_from_dimensions_without_dpi() -> None:
    _, scale, meta = annotate_page(_sheet(), WORDS, "ocr", dpi=None)
    # 1000 mm / 100 px and 2000 mm / 200 px: 10 mm per pixel, two labels agree.
    assert scale == pytest.approx(10.0)
    assert meta["scale_method"] == "dimension_fit"
    assert meta["scale_support"] == 2
    assert meta["scale_known"] is True


def test_ticks_read_as_text_are_not_erased() -> None:
    # Tesseract reads extension lines as "|" words (seen on real pages, #69). Erasing
    # those boxes would wipe the ticks, so the fit must still find 10 mm per pixel.
    bars = [Word((float(x), 88.0, x + 1.0, 113.0), "|") for x in (50, 150, 350)]
    _, scale, meta = annotate_page(_sheet(), [*WORDS, *bars], "ocr", dpi=None)
    assert scale == pytest.approx(10.0)
    assert meta["scale_support"] == 2


def test_no_scale_when_nothing_to_fit() -> None:
    _, scale, meta = annotate_page(_sheet(), WORDS[:1], "ocr", dpi=None)
    assert scale is None  # one label alone is not trusted
    assert meta["scale_method"] is None
    assert meta["scale_known"] is False
