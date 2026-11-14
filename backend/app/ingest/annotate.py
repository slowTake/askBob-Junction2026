"""Shared page pipeline for PDFs and images: words -> classified elements -> geometry."""

from typing import Any

from app.domain.areas import outline_agrees
from app.domain.dimensions import mm_per_px
from app.domain.geometry import Point, bbox_center, bbox_to_plan_polygon, footprint_mm
from app.domain.kinds import DrawingKind
from app.domain.labels import Label, link_room_labels, unnumbered_are_legend
from app.domain.polygons import polygon_bbox
from app.domain.tokens import Word, classify, merge_split_numbers
from app.ingest.dimension_lines import fit_dimension_scale
from app.ingest.rooms import Gray, ink_mask, room_region, wall_boxes
from app.ingest.types import ExtractedElement

WALL_CONFIDENCE = 0.3  # heuristic wall detection: the agent must verify visually
VECTOR_WALL_CONFIDENCE = 0.95  # hatched regions from the PDF's vector layer
WALL: DrawingKind = "wall"


def annotate_page(
    gray: Gray,
    words: list[Word],
    source: str,
    dpi: float | None,
    vector_walls: list[list[Point]] | None = None,
) -> tuple[list[ExtractedElement], float | None, dict[str, Any]]:
    """Return the page's elements, its mm-per-pixel scale (if known) and page metadata.

    `vector_walls` are exact wall outlines in page pixels (from a PDF's vector
    layer); when given, they replace the pixel-based wall heuristic.
    """
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

    _link_printed_labels(elements)

    height = float(gray.shape[0])
    ink = ink_mask(gray)
    text_boxes = [w.bbox for w in words]

    scale_mm: float | None = None
    scale_meta: dict[str, Any] = {"scale_method": None}
    if dpi and scales:
        scale_mm = mm_per_px(dpi, scales[0])
        scale_meta["scale_method"] = "dpi"
    else:  # no DPI or no scale note: fit the printed dimensions to their dimension lines
        dimensions = [
            (el.value_mm, el.bbox)
            for el in elements
            if el.kind == "dimension" and el.value_mm and el.bbox
        ]
        fit = fit_dimension_scale(ink, dimensions, erase=text_boxes)
        if fit:
            scale_mm, support = fit
            scale_meta = {"scale_method": "dimension_fit", "scale_support": support}
    # TODO(scale): scale bars (HABS, Finna) as a third method, "scale_bar".

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
            measured = round(area_px * scale_mm * scale_mm / 1e6, 2)
            if not outline_agrees(measured, el.properties.get("printed_area_m2")):
                el.properties["region"] = "disagrees_with_printed_area"
                del el.properties["polygon_px"]
                continue
            el.properties["measured_area_m2"] = measured
            el.properties.setdefault("area_m2", measured)
            el.footprint_mm = footprint_mm(polygon, scale_mm, height)

    if vector_walls:
        for outline in vector_walls:
            wall = ExtractedElement(
                kind=WALL, source="pdf_vector", bbox=polygon_bbox(outline),
                confidence=VECTOR_WALL_CONFIDENCE,
                properties={"polygon_px": [list(p) for p in outline]},
            )  # fmt: skip
            if scale_mm:
                wall.footprint_mm = footprint_mm(outline, scale_mm, height)
            elements.append(wall)
    else:
        for box in wall_boxes(ink):
            wall = ExtractedElement(
                kind=WALL, source="derived", bbox=box, confidence=WALL_CONFIDENCE
            )
            if scale_mm:
                wall.footprint_mm = bbox_to_plan_polygon(box, scale_mm, height)
            elements.append(wall)

    meta = {
        "scale_denominators": scales,
        "scale_known": scale_mm is not None,
        **scale_meta,
        "words": len(words),
    }
    return elements, scale_mm, meta


def _link_printed_labels(elements: list[ExtractedElement]) -> None:
    """Give each room its printed number and area ("Zimmer / 2.01 / 15.61 m²").

    A printed area is exact (it comes from the architect's model), so it wins over
    any area we measure from pixels.
    """
    labels = [Label(e.kind, e.bbox) for e in elements if e.bbox is not None]
    indexed = [e for e in elements if e.bbox is not None]
    links = link_room_labels(labels)
    rooms = [i for i, lb in enumerate(labels) if lb.kind == "room"]
    numbered = sum(1 for i in rooms if "room_number" in links.get(i, {}))
    if unnumbered_are_legend(numbered, len(rooms) - numbered):
        for i in rooms:
            if "room_number" not in links.get(i, {}):
                indexed[i].kind = "text"  # a legend entry, e.g. "WC" in the key box
                indexed[i].properties["legend"] = True
    for room_i, found in links.items():
        room = indexed[room_i]
        if "room_number" in found:
            number = indexed[found["room_number"]].label
            room.properties["number"] = number
            room.name = f"{room.name} {number}"
        if "area" in found:
            area = indexed[found["area"]].properties["area_m2"]
            room.properties["printed_area_m2"] = area
            room.properties["area_m2"] = area
