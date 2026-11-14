"""Shared page pipeline for PDFs and images: words -> classified elements -> geometry."""

from typing import Any

from app.domain.dimensions import mm_per_px
from app.domain.geometry import bbox_center, bbox_to_plan_polygon, footprint_mm
from app.domain.kinds import DrawingKind
from app.domain.tokens import Word, classify, merge_split_numbers
from app.ingest.rooms import Gray, ink_mask, room_region, wall_boxes
from app.ingest.types import ExtractedElement

WALL_CONFIDENCE = 0.3  # heuristic wall detection: the agent must verify visually
WALL: DrawingKind = "wall"


def annotate_page(
    gray: Gray, words: list[Word], source: str, dpi: float | None
) -> tuple[list[ExtractedElement], float | None, dict[str, Any]]:
    """Return the page's elements, its mm-per-pixel scale (if known) and page metadata."""
    words = merge_split_numbers(words)
    elements: list[ExtractedElement] = []
    scales: list[int] = []
    for word in words:
        c = classify(word.text)
        if c.kind == "scale":
            scales.append(int(c.properties["denominator"]))
        elements.append(
            ExtractedElement(
                kind=c.kind,
                source=source,
                text=word.text,
                label=c.label,
                name=c.name,
                value_mm=c.value_mm,
                bbox=word.bbox,
                properties=c.properties,
                confidence=word.confidence,
            )
        )

    # TODO(scale): raster pages without DPI: fit dimension strings to their dimension lines.
    scale_mm = mm_per_px(dpi, scales[0]) if dpi and scales else None
    height = float(gray.shape[0])
    ink = ink_mask(gray)
    text_boxes = [w.bbox for w in words]

    for el in elements:
        if el.kind != "room" or el.bbox is None:
            continue
        found = room_region(ink, bbox_center(el.bbox), erase=text_boxes, close_px=3)
        if found is None:
            el.properties["region"] = "not_closed"
            continue
        polygon, area_px = found
        el.properties["polygon_px"] = [list(p) for p in polygon]
        if scale_mm:
            el.properties["area_m2"] = round(area_px * scale_mm * scale_mm / 1e6, 2)
            el.footprint_mm = footprint_mm(polygon, scale_mm, height)

    for box in wall_boxes(ink):
        wall = ExtractedElement(kind=WALL, source="derived", bbox=box, confidence=WALL_CONFIDENCE)
        if scale_mm:
            wall.footprint_mm = bbox_to_plan_polygon(box, scale_mm, height)
        elements.append(wall)

    meta = {"scale_denominators": scales, "scale_known": scale_mm is not None, "words": len(words)}
    return elements, scale_mm, meta
