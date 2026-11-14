"""Tesseract OCR for raster drawings, reading horizontal and vertical text."""

import logging
from functools import lru_cache

import cv2
import pytesseract

from app.domain.geometry import bbox_iou, scale_bbox, unrotate_bbox_cw90
from app.domain.tokens import Word, merge_split_numbers
from app.ingest.rooms import Gray

log = logging.getLogger(__name__)
MIN_CONFIDENCE = 30.0  # tesseract confidence, 0..100


def pick_langs(requested: str, available: set[str]) -> str:
    """Keep the requested languages that are installed; fall back to English."""
    langs = [lang for lang in requested.split("+") if lang in available]
    return "+".join(langs) if langs else "eng"


@lru_cache
def _available_langs() -> frozenset[str]:
    return frozenset(pytesseract.get_languages(config=""))


def ocr_words(gray: Gray, requested_langs: str) -> list[Word]:
    """OCR the page, then again rotated 90° clockwise to catch vertical dimension text."""
    langs = pick_langs(requested_langs, set(_available_langs()))
    factor = upscale_factor(max(gray.shape[:2]))
    image = gray
    if factor > 1:  # tesseract wants text ~20-30 px tall; small scans are upscaled first
        image = cv2.resize(gray, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
    words = _ocr(image, langs)
    rotated = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    height = float(image.shape[0])
    # Join "2" + "400" while they still sit side by side: unrotated, they are stacked
    # and merge_split_numbers in annotate_page would leave "400" as a 400 mm dimension.
    for word in merge_split_numbers(_ocr(rotated, langs)):
        bbox = unrotate_bbox_cw90(word.bbox, height)
        if all(bbox_iou(bbox, w.bbox) < 0.5 for w in words):
            words.append(Word(bbox, word.text, word.confidence))
    return [Word(scale_bbox(w.bbox, 1 / factor), w.text, w.confidence) for w in words]


def upscale_factor(longest_side_px: int, target_px: int = 3000, max_factor: int = 4) -> int:
    """Integer upscale so the longest side reaches about `target_px`, capped."""
    if longest_side_px <= 0 or longest_side_px >= target_px:
        return 1
    return min(max_factor, -(-target_px // longest_side_px))  # ceiling division


def _ocr(image: Gray, langs: str) -> list[Word]:
    # psm 11 = sparse text: drawings are scattered labels, not paragraphs.
    data = pytesseract.image_to_data(
        image, lang=langs, config="--psm 11", output_type=pytesseract.Output.DICT
    )
    words: list[Word] = []
    for i, raw in enumerate(data["text"]):
        text = str(raw).strip()
        conf = float(data["conf"][i])
        if not text or conf < MIN_CONFIDENCE:
            continue
        x, y, w, h = (float(data[k][i]) for k in ("left", "top", "width", "height"))
        words.append(Word((x, y, x + w, y + h), text, conf / 100))
    return words
