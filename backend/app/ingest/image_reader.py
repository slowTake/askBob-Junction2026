"""Raster drawings (PNG, JPEG, TIFF, WebP, BMP, GIF): OCR plus computer vision.

Multi-page TIFFs become multi-page documents.
"""

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence, UnidentifiedImageError

from app.config import Settings
from app.domain.redraw_confidence import CONFIDENCE_KEY, confidence_meta, shapes_of
from app.domain.redraw_mode import STATS_KEY, stats_meta
from app.ingest.annotate import annotate_page
from app.ingest.confidence import score_redraw
from app.ingest.errors import ReaderError
from app.ingest.ink import separate_colours
from app.ingest.ocr_client import page_words
from app.ingest.page_stats import page_stats
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
            _on_white(f)
            for _, f in zip(range(MAX_PAGES), ImageSequence.Iterator(opened), strict=False)
        ]
    if not frames:
        raise ReaderError("empty_drawing")
    file_dpi = float(dpi_info[0]) if dpi_info and dpi_info[0] > 1 else None

    pages = []
    for index, image in enumerate(frames):

        def report(stage: str, fraction: float, page_index: int = index) -> None:
            progress(stage, (page_index + fraction) / len(frames))

        pages.append(_page(index, image, file_dpi, settings, report))
    return ExtractedDocument(
        pages=pages, meta={"page_count": len(pages), "dpi_from_file": file_dpi is not None}
    )


def _on_white(frame: Image.Image) -> Image.Image:
    """Transparent drawing paper is white, including palette PNGs with transparency."""
    rgba = frame.convert("RGBA")
    paper = Image.new("RGBA", rgba.size, "white")
    return Image.alpha_composite(paper, rgba).convert("RGB")


def _page(
    index: int, image: Image.Image, dpi: float | None, settings: Settings, progress: Progress
) -> ExtractedPage:
    factor = min(1.0, MAX_SIDE_PX / max(image.size))
    if factor < 1.0:
        image = image.resize((round(image.width * factor), round(image.height * factor)))
        dpi = dpi * factor if dpi else None
    # Fills and red labels are taken off the line work before anything thresholds it (D-051).
    layers = separate_colours(np.asarray(image, dtype=np.uint8))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png = buffer.getvalue()
    progress("ocr", 0.0)
    words = page_words(layers.ocr_page, settings)
    progress("vision", 0.3)
    vision, status = analyse_page(png, settings)
    progress("annotating", 0.8)
    elements, scale_mm, meta = annotate_page(layers.ink_page, words, "ocr", dpi, vision=vision)
    progress("annotating", 1.0)
    meta["vision"] = status
    # What the page looks like decides its redraw: a printed plan or a sketch (#138).
    dimensions = sum(1 for e in elements if e.kind == "dimension")
    meta[STATS_KEY] = stats_meta(page_stats(layers, dimensions))
    # How much of the page's own ink the Redrawn view accounts for (#132).
    meta[CONFIDENCE_KEY] = confidence_meta(score_redraw(layers, shapes_of(elements, image.width)))
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
