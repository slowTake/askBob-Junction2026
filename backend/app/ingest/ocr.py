"""OCR for raster drawings: RapidOCR first (D-024), Tesseract as the fallback.

RapidOCR is PaddleOCR's neural text detector and recogniser on ONNX Runtime (models
ship in the wheel). It finds small text Tesseract misses: 86% of Swiss room numbers
at 150 DPI, against 42%. It reads a large page in overlapping tiles.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any

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


def ocr_words(gray: Gray, requested_langs: str, engine: str = "rapid") -> list[Word]:
    """Words with boxes in page pixels. Any RapidOCR failure falls back to Tesseract."""
    if engine == "rapid":
        try:
            return _rapid_words(gray)
        except Exception:
            log.warning("RapidOCR failed; reading the page with Tesseract", exc_info=True)
    return _tesseract_words(gray, requested_langs)


def _tesseract_words(gray: Gray, requested_langs: str) -> list[Word]:
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


# --- RapidOCR -------------------------------------------------------------------

RAPID_TILE, RAPID_OVERLAP = 1600, 200
RAPID_MIN_SCORE = 0.5
RAPID_SMALL_PAGE_PX = 4000  # pages below this are enlarged x2: text ~12 px -> ~24 px
_NON_LATIN = re.compile(r"[^\x20-\x7E\u00A0-\u024F²³°]")
_EDGE_PUNCT = ".,;:!?|[](){}'\"`"


def clean_text(text: str) -> str:
    """Drop non-Latin noise (the default model also reads CJK) and stray edge punctuation."""
    return _NON_LATIN.sub("", text).strip().strip(_EDGE_PUNCT).strip()


def tile_starts(length: int, tile: int, overlap: int) -> list[int]:
    if length <= tile:
        return [0]
    return sorted({*range(0, length - tile, tile - overlap), length - tile})


def dedupe_words(words: list[Word]) -> list[Word]:
    """Tiles overlap, so words near their edges are read twice: keep the surer one."""
    kept: list[Word] = []
    for w in sorted(words, key=lambda w: -w.confidence):
        if all(bbox_iou(w.bbox, k.bbox) < 0.3 for k in kept):
            kept.append(w)
    return sorted(kept, key=lambda w: (w.bbox[1], w.bbox[0]))


_CUDA = {"on": False}


def use_cuda(on: bool) -> None:
    """Run RapidOCR's models on CUDA (the OCR service on a GPU host, #119)."""
    _CUDA["on"] = on
    _rapid_engine.cache_clear()


@lru_cache
def _rapid_engine() -> Any:
    from rapidocr_onnxruntime import RapidOCR

    if not _CUDA["on"]:
        return RapidOCR()
    return RapidOCR(det_use_cuda=True, cls_use_cuda=True, rec_use_cuda=True)


def _rapid_words(gray: Gray) -> list[Word]:
    factor = 2.0 if max(gray.shape[:2]) < RAPID_SMALL_PAGE_PX else 1.0
    image = gray
    if factor > 1:
        image = cv2.resize(gray, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
    rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    h, w = image.shape[:2]
    engine = _rapid_engine()
    jobs = [(x, y) for y in tile_starts(h, RAPID_TILE, RAPID_OVERLAP)
            for x in tile_starts(w, RAPID_TILE, RAPID_OVERLAP)]  # fmt: skip

    def read(xy: tuple[int, int]) -> list[Word]:
        x, y = xy
        tile = rgb[y : y + RAPID_TILE, x : x + RAPID_TILE]
        if tile.min() > 200:  # blank paper
            return []
        result, _ = engine(tile)
        out = []
        for quad, raw, score in result or []:
            text = clean_text(str(raw))
            if not text or float(score) < RAPID_MIN_SCORE:
                continue
            xs = [p[0] for p in quad]
            ys = [p[1] for p in quad]
            box = (x + min(xs), y + min(ys), x + max(xs), y + max(ys))
            out.append(Word(scale_bbox(box, 1 / factor), text, float(score)))
        return out

    with ThreadPoolExecutor(max_workers=4) as pool:
        words = [word for part in pool.map(read, jobs) for word in part]
    return dedupe_words(words)
