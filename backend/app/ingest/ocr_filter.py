"""Drop OCR words that are line work, not text (#90).

On plans, OCR reads hatching, dashed lines, symbol frames and solid blocks as words
("==", "|", "o", "TT", "mm"). Tesseract's confidence doesn't tell them apart: a
stove can come back at 0.87 while a real room code ("H", "K") is a single letter at
0.6. What does tell them apart is the ink inside the word's own box: text is several
glyph-sized marks, line work is one mark that is a line, a solid block or a frame.

Each box is thresholded on its own (Otsu on the crop), so a label printed on a grey
room fill is judged against that fill, not against the page's white paper.
"""

import re
from typing import Any

import cv2
import numpy as np
import numpy.typing as npt

from app.domain.tokens import Word

Gray = npt.NDArray[Any]

HAS_WORD = re.compile(r"[^\W_]")  # a letter or digit in any script
MIN_CONTRAST = 32  # grey range below this is too flat to judge: keep the word
DOMINANT = 0.8  # one mark holding this share of the box's ink decides its shape
LINE_WIDE = 5.0  # a mark this many times wider than tall is a line
LINE_TALL = 8.0  # ...or this many times taller than wide ("I" and "1" are about 7)
SPAN = 0.9  # a block or frame covers this share of the box both ways
SOLID_FILL = 0.9  # a block fills this share of its own box
FRAME_HOLE = 0.5  # a frame's holes cover this share of its own box (an "O" is about 0.4)


def drop_line_work(gray: Gray, words: list[Word]) -> list[Word]:
    """The words worth keeping: with a letter or digit, and not drawn by line work.

    `gray` is the page the boxes refer to (page pixels).
    """
    return [w for w in words if HAS_WORD.search(w.text) and not is_line_work(_crop(gray, w))]


def is_line_work(crop: Gray) -> bool:
    """Whether the ink in a word's box is one line, block or frame rather than glyphs."""
    if crop.size == 0 or int(crop.max()) - int(crop.min()) < MIN_CONTRAST:
        return False
    _, binary = cv2.threshold(crop, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count < 2:
        return False
    marks = stats[1:]
    biggest = int(np.argmax(marks[:, cv2.CC_STAT_AREA]))
    _, _, w, h, area = (int(v) for v in marks[biggest])
    if area < DOMINANT * int(marks[:, cv2.CC_STAT_AREA].sum()):
        return False  # several marks share the ink: glyphs
    if w >= LINE_WIDE * h or h >= LINE_TALL * w:
        return True
    box_h, box_w = crop.shape
    if min(w / box_w, h / box_h) < SPAN:
        return False
    if area >= SOLID_FILL * w * h:
        return True
    return _enclosed(labels == biggest + 1) >= FRAME_HOLE * w * h


def _enclosed(mark: npt.NDArray[np.bool_]) -> int:
    """Paper pixels the mark closes in (its holes), counted, not traced."""
    ink = mark.astype(np.uint8)
    outer, _ = cv2.findContours(ink, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(ink)
    cv2.drawContours(filled, outer, -1, 1, thickness=cv2.FILLED)
    return int(filled.sum()) - int(ink.sum())


def _crop(gray: Gray, word: Word) -> Gray:
    x0, y0, x1, y1 = (round(v) for v in word.bbox)
    crop: Gray = gray[max(0, y0) : max(0, y1), max(0, x0) : max(0, x1)]
    return crop
