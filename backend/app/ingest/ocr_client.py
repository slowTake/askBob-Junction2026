"""A page's OCR words: from the OCR service when `OCR_URL` is set (#119), else locally.

The service runs the same `ocr_words` on a bigger machine (a Verda GPU host). Any
failure (unreachable, timeout, error, malformed answer) reads the page locally
instead, so a missing service makes ingest slower, never broken.
"""

import json
import logging
import urllib.parse
import urllib.request

import cv2

from app.config import Settings
from app.domain.ocr_wire import parse_words
from app.domain.tokens import Word
from app.ingest.ocr import ocr_words
from app.ingest.ocr_filter import drop_line_work
from app.ingest.rooms import Gray

log = logging.getLogger(__name__)


def page_words(gray: Gray, settings: Settings) -> list[Word]:
    """The page's words, without the line work OCR read as words (D-052)."""
    return drop_line_work(gray, _read(gray, settings))


def _read(gray: Gray, settings: Settings) -> list[Word]:
    if settings.ocr_url:
        words = _remote(gray, settings)
        if words is not None:
            return words
    return ocr_words(gray, settings.ocr_langs, settings.ocr_engine)


def _remote(gray: Gray, settings: Settings) -> list[Word] | None:
    ok, png = cv2.imencode(".png", gray)
    if not ok:
        return None
    query = urllib.parse.urlencode({"langs": settings.ocr_langs, "engine": settings.ocr_engine})
    request = urllib.request.Request(
        f"{str(settings.ocr_url).rstrip('/')}/ocr?{query}",
        data=png.tobytes(),
        headers={"Content-Type": "image/png"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.ocr_timeout_s) as response:
            body = json.loads(response.read())
    except (OSError, ValueError):  # URLError, HTTPError and timeouts are OSErrors
        log.warning("OCR service failed; reading the page locally", exc_info=True)
        return None
    words = parse_words(body.get("data")) if isinstance(body, dict) and body.get("ok") else None
    if words is None:
        log.warning("OCR service answer unusable; reading the page locally")
    return words
