"""Raster drawings (PNG, JPEG, TIFF, WebP, BMP, GIF): OCR plus computer vision.

Multi-page TIFFs become multi-page documents.
"""

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence, UnidentifiedImageError

from app.config import Settings
from app.ingest.annotate import annotate_page
from app.ingest.errors import ReaderError
from app.ingest.ocr import ocr_words
from app.ingest.types import ExtractedDocument, ExtractedPage, Progress
from app.ingest.vision_client import analyse_page

MAX_SIDE_PX = 8000  # bigger scans are downscaled; bboxes refer to the stored image
MAX_PAGES = 50
Image.MAX_IMAGE_PIXELS = 400_000_000  # large-format scans are legitimate, but not unbounded


def read_image(path: Path, settings: Settings, progress: Progress) -> ExtractedDocument:
    try:
        opened = Image.open(path)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ReaderError("unreadable_file", "not a readable image") from exc
    with opened:
        dpi_info = opened.info.get("dpi")
        frames = [
            f.convert("RGB")
            for _, f in zip(range(MAX_PAGES), ImageSequence.Iterator(opened), strict=False)
        ]
    if not frames:
        raise ReaderError("empty_drawing")
    file_dpi = float(dpi_info[0]) if dpi_info and dpi_info[0] > 1 else None

    pages = []
    for index, image in enumerate(frames):
        pages.append(_page(index, image, file_dpi, settings))
        progress("ocr", (index + 1) / len(frames))
    return ExtractedDocument(
        pages=pages, meta={"page_count": len(pages), "dpi_from_file": file_dpi is not None}
    )


def _page(index: int, image: Image.Image, dpi: float | None, settings: Settings) -> ExtractedPage:
    factor = min(1.0, MAX_SIDE_PX / max(image.size))
    if factor < 1.0:
        image = image.resize((round(image.width * factor), round(image.height * factor)))
        dpi = dpi * factor if dpi else None
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png = buffer.getvalue()
    words = ocr_words(gray, settings.ocr_langs)
    vision, status = analyse_page(png, settings)
    elements, scale_mm, meta = annotate_page(gray, words, "ocr", dpi, vision=vision)
    meta["vision"] = status
    return ExtractedPage(
        index=index,
        image_png=png,
        width_px=image.width,
        height_px=image.height,
        dpi=dpi,
        mm_per_px=scale_mm,
        elements=elements,
        meta=meta,
    )
