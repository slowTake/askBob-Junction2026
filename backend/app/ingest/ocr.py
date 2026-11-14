"""Tesseract OCR for raster drawings, reading horizontal and vertical text."""

import logging
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import cv2
import pytesseract

from app.domain.geometry import bbox_iou, scale_bbox, unrotate_bbox_cw90
from app.domain.tokens import Word
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
    rotated = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    # The two passes are independent tesseract processes: run them side by side.
    with ThreadPoolExecutor(max_workers=2) as pool:
        upright = pool.submit(_ocr, image, langs)
        sideways = pool.submit(_ocr, rotated, langs)
        words, rotated_words = upright.result(), sideways.result()
    height = float(image.shape[0])
    for word in rotated_words:
        bbox = unrotate_bbox_cw90(word.bbox, height)
        if all(bbox_iou(bbox, w.bbox) < 0.5 for w in words):
            words.append(Word(bbox, word.text, word.confidence))
    return [Word(scale_bbox(w.bbox, 1 / factor), w.text, w.confidence) for w in words]


def upscale_factor(longest_side_px: int, target_px: int = 3500, max_factor: float = 4.0) -> float:
    """Scale so the longest side reaches `target_px` (never shrinks, capped at `max_factor`).

    3500 px measured best on the dataset: smaller loses small text like room numbers,
    larger was slower without finding more (Swiss plan: 3000 -> 29 numbers, 3500 -> 30).
    """
    if longest_side_px <= 0 or longest_side_px >= target_px:
        return 1.0
    return min(max_factor, target_px / longest_side_px)


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
