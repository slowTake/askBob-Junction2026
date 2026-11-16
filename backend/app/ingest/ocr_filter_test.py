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


def _glyphs(count: int) -> np.ndarray:
    # `count` H-shaped glyphs, 14 x 10 each, 2 px apart: separate glyph-sized marks.
    return np.hstack([np.hstack([_letter_h(), _crop(14, 2)]) for _ in range(count)])


def _stove() -> np.ndarray:
    # A stove symbol read as "1281" on colorful-34: a frame open at the top (a wall below
    # it closes the bottom) round four burner dots, in a 23 x 26 box.
    crop = _crop(23, 26)
    crop[3:23, 2:4] = INK  # left side: rows 3-22, 20 of the 23 rows
    crop[3:23, 21:23] = INK  # right side: the same rows
    crop[20:23, :] = INK  # bottom: all 26 columns
    for y, x in ((6, 7), (6, 14), (13, 7), (13, 14)):
        crop[y : y + 4, x : x + 4] = INK  # four 4 x 4 dots inside
    return crop


class TestIsLineWork:
    def test_a_horizontal_line_is_line_work(self) -> None:
        # One mark 40 px wide and 2 px tall: 20:1, over the 5:1 limit.
        crop = _crop(6, 40)
        crop[2:4, :] = INK
        assert is_line_work(crop, 1)

    def test_a_long_vertical_line_is_line_work_but_an_upright_letter_is_not(self) -> None:
        line = _crop(32, 6)
        line[1:31, 2:4] = INK  # 30 x 2: 15:1, over the 8:1 limit
        assert is_line_work(line, 1)
        letter = _crop(16, 6)
        letter[1:15, 2:4] = INK  # 14 x 2: 7:1, an "I" or a "1"
        assert not is_line_work(letter, 1)

    def test_a_solid_block_is_line_work(self) -> None:
        # A 19 x 19 block in a 20 x 20 box: fully filled and spanning 0.95 of it.
        crop = _crop(20, 20)
        crop[:19, :19] = INK
        assert is_line_work(crop, 1)

    def test_a_frame_is_line_work(self) -> None:
        # A 1 px square outline round a 20 x 20 box: its hole is about 18 x 18 of 20 x 20.
        crop = _crop(20, 20)
        crop[0, :] = crop[-1, :] = INK
        crop[:, 0] = crop[:, -1] = INK
        assert is_line_work(crop, 1)

    def test_letters_are_not_line_work(self) -> None:
        assert not is_line_work(_letter_h(), 1)  # no hole, upright
        assert not is_line_work(_letter_o(), 1)  # a hole of 0.4, under the 0.5 limit

    def test_two_letters_side_by_side_are_not_line_work(self) -> None:
        # "OH": neither mark holds 80% of the ink.
        assert not is_line_work(np.hstack([_letter_o()[:12], _letter_h()[:12]]), 2)

    def test_a_label_on_a_grey_fill_is_judged_against_the_fill(self) -> None:
        # On a page-wide threshold the grey fill (200) would be ink and the box a
        # solid block; against its own background the H is a letter.
        assert not is_line_work(_letter_h(background=200), 1)

    def test_a_box_too_flat_to_judge_is_kept(self) -> None:
        assert not is_line_work(_crop(10, 10, background=200), 1)
        assert not is_line_work(np.zeros((0, 0), np.uint8), 1)

    def test_an_open_frame_round_a_symbol_is_line_work(self) -> None:
        # The frame is 2 x 20 x 2 = 80 px of sides + 3 x 26 = 78 px of bottom - 12 px where
        # they overlap = 146 px against 4 x 16 = 64 px of dots: 0.70 of the ink, under the
        # 0.8 that would let one mark decide alone, and it has no hole (open at the top).
        # It draws three straight sides of the box: within the outer 5 px (0.2 of 23 and
        # of 26), row 20 is 26/26 ink and columns 2 and 21 are 20/23 = 0.87 ink, all at
        # least 0.8; the top's best row (3) is 4/26 = 0.15. Glyphs of a four-character
        # word can't do that, so the word is line work.
        assert is_line_work(_stove(), 4)

    def test_one_letter_may_run_along_three_sides_of_its_own_box(self) -> None:
        # A "U": uprights in columns 1-2 and 7-8, joined along rows 12-13. It draws
        # the left (column 1, 14/14), right (column 8, 14/14) and bottom (row 12, 8/10 =
        # 0.8) of its box, as a symbol frame does, but a one-letter word's box is that
        # letter's box.
        crop = _crop(14, 10)
        crop[:, 1:3] = INK
        crop[:, 7:9] = INK
        crop[12:14, 1:9] = INK
        assert not is_line_work(crop, 1)

    def test_a_label_in_a_room_corner_is_not_line_work(self) -> None:
        # Three glyphs under a wall corner (top row and left column, joined): the corner
        # draws two sides of the box (top 40/40, left 18/18), not three.
        glyphs = _glyphs(3)  # 14 x 36
        crop = _crop(18, 40)
        crop[3:17, 3:39] = glyphs
        crop[0, :] = INK
        crop[:, 0] = INK
        assert not is_line_work(crop, 3)

    def test_a_wobbly_handwritten_loop_round_the_box_is_not_a_frame(self) -> None:
        # One joined stroke, 1 px thick, round the left, bottom and right of a 20 x 60 box
        # (a handwritten word like "pesutone" on colorful-2194), zigzagging 3 px:
        # bottom y = 16 + |x mod 6 - 3|, left x = |y mod 6 - 3|, right x = 59 - that.
        # It fills each side's band (the outer 4 rows, 12 columns), but no single row or
        # column there is straight: the fullest row, 18, holds 20 bottom pixels and one
        # each of the sides, 22/60 = 0.37; the fullest column, 57, holds 7 of the right
        # side and 1 of the bottom, 8/20 = 0.4; all under 0.8.
        crop = _crop(20, 60)
        for x in range(60):
            crop[16 + abs(x % 6 - 3), x] = INK
        for y in range(20):
            crop[y, abs(y % 6 - 3)] = INK
            crop[y, 59 - abs(y % 6 - 3)] = INK
        assert not is_line_work(crop, 8)


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

    def test_keeps_short_labels_heights_and_decimal_comma_dimensions(self) -> None:
        # Room codes, a ceiling height and a decimal-comma dimension, each drawn as one
        # glyph-sized mark per character (the comma as a 2 x 2 dot): none is dropped.
        texts = ["MH", "OH", "WC", "KPH", "S", "h1600", "5,341"]
        page = _crop(20, 20 + 12 * 7 * len(texts))
        words = []
        x = 10
        for text in texts:
            glyphs = _glyphs(len(text))
            page[3:17, x : x + glyphs.shape[1]] = glyphs
            if "," in text:
                page[15:17, x + 10 : x + 12] = INK  # the comma in the 2 px gap after "5"
            words.append(Word((x, 3, x + glyphs.shape[1], 17), text, 0.6))
            x += glyphs.shape[1] + 8
        assert [w.text for w in drop_line_work(page, words)] == texts

    def test_drops_a_symbol_read_as_digits(self) -> None:
        page = _crop(40, 40)
        page[5:28, 5:31] = _stove()
        assert drop_line_work(page, [Word((5, 5, 31, 28), "1281", 0.54)]) == []
