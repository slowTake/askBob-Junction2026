import numpy as np
import pytest

from app.ingest.dimension_lines import dimension_span, fit_dimension_scale
from app.ingest.rooms import ink_mask

# A 12 px tall label above the segment between x = 50 and x = 150 of a dimension line.
LABEL = (85.0, 84.0, 115.0, 96.0)


def _chain(ticks: str = "extension") -> np.ndarray:
    """200x400 white page with one dimension chain, drawn with exact numpy slices.

    Dimension line: row 100, columns 40..360. Ticks at x = 50, 150 and 350, either
    vertical extension lines (rows 88..112) or 45° slashes through (x, 100).
    The label is a solid block inside LABEL so it has ink like real text.
    """
    page = np.full((200, 400), 255, np.uint8)
    page[100, 40:361] = 0
    for x in (50, 150, 350):
        if ticks == "extension":
            page[88:113, x] = 0
        else:
            for k in range(-7, 8):
                page[100 - k, x + k] = 0
    page[85:96, 86:114] = 0
    return page


def test_span_between_extension_lines() -> None:
    # The label sits over the segment from x = 50 to x = 150: 150 - 50 = 100 px.
    assert dimension_span(ink_mask(_chain()), LABEL, erase=[LABEL]) == pytest.approx(100.0)


def test_span_between_slash_ticks() -> None:
    # Slashes are symmetric about their crossing with the line, so the same 100 px.
    span = dimension_span(ink_mask(_chain("slash")), LABEL, erase=[LABEL])
    assert span == pytest.approx(100.0, abs=0.5)


def test_span_of_vertical_dimension() -> None:
    # The same chain turned on its side: page transposed, label box (x, y) swapped.
    page = _chain().T.copy()
    label = (LABEL[1], LABEL[0], LABEL[3], LABEL[2])
    assert dimension_span(ink_mask(page), label, erase=[label]) == pytest.approx(100.0)


def test_no_line_near_label() -> None:
    page = np.full((200, 400), 255, np.uint8)
    page[85:96, 86:114] = 0
    assert dimension_span(ink_mask(page), LABEL, erase=[LABEL]) is None


def test_line_without_a_tick_on_one_side() -> None:
    page = _chain()
    page[88:113, 50] = 255  # remove the left extension line
    page[100, 40:60] = 255  # and the line now just ends at x = 60
    assert dimension_span(ink_mask(page), LABEL, erase=[LABEL]) is None


def test_fit_needs_agreeing_dimensions() -> None:
    page = _chain()
    second = (235.0, 84.0, 265.0, 96.0)  # over the segment 150..350 (200 px)
    page[85:96, 236:264] = 0
    ink = ink_mask(page)
    # 1000 mm over 100 px and 2000 mm over 200 px: both 10 mm per pixel.
    assert fit_dimension_scale(ink, [(1000.0, LABEL), (2000.0, second)]) == (10.0, 2)
    # A misread "5000" over 200 px says 25 mm/px: no two labels agree, so no scale.
    assert fit_dimension_scale(ink, [(1000.0, LABEL), (5000.0, second)]) is None
