"""Raster drawings (PNG, JPEG, TIFF): OCR plus computer vision."""

import io
from pathlib import Path

import numpy as np
from PIL import Image

from app.config import Settings
from app.ingest.annotate import annotate_page
from app.ingest.ocr import ocr_words
from app.ingest.types import ExtractedDocument, ExtractedPage, Progress

MAX_SIDE_PX = 8000  # bigger scans are downscaled; bboxes refer to the stored image


def read_image(path: Path, settings: Settings, progress: Progress) -> ExtractedDocument:
    with Image.open(path) as opened:
        image = opened.convert("RGB")  # first frame of multi-page TIFFs
        dpi_info = opened.info.get("dpi")
    dpi = float(dpi_info[0]) if dpi_info and dpi_info[0] > 1 else None

    factor = min(1.0, MAX_SIDE_PX / max(image.size))
    if factor < 1.0:
        image = image.resize((round(image.width * factor), round(image.height * factor)))
        dpi = dpi * factor if dpi else None

    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    progress("ocr", 0.2)
    words = ocr_words(gray, settings.ocr_langs)
    progress("analysing", 0.6)
    elements, scale_mm, meta = annotate_page(gray, words, "ocr", dpi)
    meta["dpi_from_file"] = dpi is not None

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    page = ExtractedPage(
        index=0,
        image_png=buffer.getvalue(),
        width_px=image.width,
        height_px=image.height,
        dpi=dpi,
        mm_per_px=scale_mm,
        elements=elements,
        meta=meta,
    )
    return ExtractedDocument(pages=[page], meta={"page_count": 1})
