import numpy as np

from app.domain.tokens import Word
from app.ingest.ocr_filter import drop_line_work, is_line_work

PAPER = 255
INK = 0


def _crop(h: int, w: int, background: int = PAPER) -> np.ndarray:
    return np.full((h, w), background, np.uint8)


def _letter_h(background: int = PAPER) -> np.ndarray:
    # A 14 x 10 crop: two 2 px uprights (columns 1-2 and 7-8) and a 2 px bar (rows 6-7).
    crop = _crop(14, 10, background)
    crop[:, 1:3] = INK
    crop[:, 7:9] = INK
    crop[6:8, 1:9] = INK
    return crop


def _letter_o() -> np.ndarray:
    # A 12 x 10 ring, 2 px thick: the hole is 8 x 6 = 48 px of the 120 px box, 0.4.
    crop = _crop(12, 10)
    crop[:, :] = INK
    crop[2:10, 2:8] = PAPER
    return crop


class TestIsLineWork:
    def test_a_horizontal_line_is_line_work(self) -> None:
        # One mark 40 px wide and 2 px tall: 20:1, over the 5:1 limit.
        crop = _crop(6, 40)
        crop[2:4, :] = INK
        assert is_line_work(crop)

    def test_a_long_vertical_line_is_line_work_but_an_upright_letter_is_not(self) -> None:
        line = _crop(32, 6)
        line[1:31, 2:4] = INK  # 30 x 2: 15:1, over the 8:1 limit
        assert is_line_work(line)
        letter = _crop(16, 6)
        letter[1:15, 2:4] = INK  # 14 x 2: 7:1, an "I" or a "1"
        assert not is_line_work(letter)

    def test_a_solid_block_is_line_work(self) -> None:
        # A 19 x 19 block in a 20 x 20 box: fully filled and spanning 0.95 of it.
        crop = _crop(20, 20)
        crop[:19, :19] = INK
        assert is_line_work(crop)

    def test_a_frame_is_line_work(self) -> None:
        # A 1 px square outline round a 20 x 20 box: its hole is about 18 x 18 of 20 x 20.
        crop = _crop(20, 20)
        crop[0, :] = crop[-1, :] = INK
        crop[:, 0] = crop[:, -1] = INK
        assert is_line_work(crop)

    def test_letters_are_not_line_work(self) -> None:
        assert not is_line_work(_letter_h())  # no hole, upright
        assert not is_line_work(_letter_o())  # a hole of 0.4, under the 0.5 limit

    def test_two_letters_side_by_side_are_not_line_work(self) -> None:
        # "OH": neither mark holds 80% of the ink.
        assert not is_line_work(np.hstack([_letter_o()[:12], _letter_h()[:12]]))

    def test_a_label_on_a_grey_fill_is_judged_against_the_fill(self) -> None:
        # On a page-wide threshold the grey fill (200) would be ink and the box a
        # solid block; against its own background the H is a letter.
        assert not is_line_work(_letter_h(background=200))

    def test_a_box_too_flat_to_judge_is_kept(self) -> None:
        assert not is_line_work(_crop(10, 10, background=200))
        assert not is_line_work(np.zeros((0, 0), np.uint8))


class TestDropLineWork:
    def test_drops_words_without_a_letter_or_digit_and_line_work(self) -> None:
        page = _crop(40, 100)
        page[5:19, 10:20] = _letter_h()  # an H at (10, 5)-(20, 19)
        page[30:32, 40:90] = INK  # a dashed line read as text
        words = [
            Word((10, 5, 20, 19), "H", 0.9),
            Word((40, 28, 90, 34), "mm", 0.86),  # letters, but the box is a line
            Word((60, 0, 70, 10), "==", 0.9),  # no letter or digit
            Word((70, 0, 80, 10), "12", 0.9),  # digits on blank paper: nothing to judge, kept
        ]
        kept = drop_line_work(page, words)
        assert [w.text for w in kept] == ["H", "12"]

    def test_keeps_letters_and_digits_from_any_script(self) -> None:
        page = _crop(20, 20)
        words = [Word((0, 0, 10, 10), "Ä", 0.5), Word((0, 0, 10, 10), "²", 0.5)]
        assert [w.text for w in drop_line_work(page, words)] == ["Ä", "²"]
