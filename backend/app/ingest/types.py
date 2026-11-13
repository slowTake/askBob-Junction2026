"""What every reader returns. Readers never touch the database; `persist.py` does."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.domain.geometry import BBox, Point

Progress = Callable[[str, float], None]  # (stage, fraction 0..1)


@dataclass
class ExtractedElement:
    kind: str
    source: str  # ifc | pdf_text | pdf_vector | ocr | derived
    text: str | None = None
    label: str | None = None
    name: str | None = None
    value_mm: float | None = None
    bbox: BBox | None = None  # page pixels of the rendered page image
    footprint_mm: list[Point] | None = None  # plan polygon, when the page scale is known
    ifc_guid: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class ExtractedPage:
    index: int
    image_png: bytes
    width_px: int
    height_px: int
    dpi: float | None
    mm_per_px: float | None
    elements: list[ExtractedElement]
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedDocument:
    pages: list[ExtractedPage] = field(default_factory=list)
    elements: list[ExtractedElement] = field(default_factory=list)  # not tied to a page (IFC)
    meta: dict[str, Any] = field(default_factory=dict)
