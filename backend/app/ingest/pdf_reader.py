"""Vector PDFs: exact text positions from the PDF itself; OCR only for scanned pages."""

from pathlib import Path

import cv2
import numpy as np
import pymupdf

from app.config import Settings
from app.domain.geometry import scale_bbox
from app.domain.tokens import Word
from app.ingest.annotate import annotate_page
from app.ingest.ocr import ocr_words
from app.ingest.types import ExtractedDocument, ExtractedPage, Progress

POINTS_PER_INCH = 72.0


def read_pdf(path: Path, settings: Settings, progress: Progress) -> ExtractedDocument:
    doc = pymupdf.open(path)
    result = ExtractedDocument(meta={"page_count": doc.page_count, "metadata": doc.metadata or {}})
    dpi = float(settings.render_dpi)
    px_per_pt = dpi / POINTS_PER_INCH
    for number in range(doc.page_count):
        page = doc.load_page(number)
        pix = page.get_pixmap(dpi=int(dpi))
        rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        gray = cv2.cvtColor(rgb[:, :, :3], cv2.COLOR_RGB2GRAY)

        words = _pdf_words(page, px_per_pt)
        source = "pdf_text"
        if not words:  # scanned page: no text layer
            words = ocr_words(gray, settings.ocr_langs)
            source = "ocr"

        elements, scale_mm, meta = annotate_page(gray, words, source, dpi)
        meta["text_layer"] = source == "pdf_text"
        # TODO(vector): walls/doors from page.get_drawings() are exact; prefer them over CV.
        result.pages.append(
            ExtractedPage(
                index=number,
                image_png=pix.tobytes("png"),
                width_px=pix.width,
                height_px=pix.height,
                dpi=dpi,
                mm_per_px=scale_mm,
                elements=elements,
                meta=meta,
            )
        )
        progress("reading", (len(result.pages)) / max(doc.page_count, 1))
    return result


def _pdf_words(page: pymupdf.Page, px_per_pt: float) -> list[Word]:
    """Words in rendered-pixel coordinates.

    PyMuPDF reports text in unrotated page space; the pixmap is rendered rotated,
    so map through `rotation_matrix` first (checked on a rotated test page).
    """
    words: list[Word] = []
    for w in page.get_text("words", sort=True):
        rect = pymupdf.Rect(w[:4]) * page.rotation_matrix
        bbox = scale_bbox((rect.x0, rect.y0, rect.x1, rect.y1), px_per_pt)
        words.append(Word(bbox, str(w[4])))
    return words
