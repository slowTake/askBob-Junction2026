"""Pure registration and fusion of a raster page with native CAD room geometry."""

from dataclasses import replace
from typing import Any

from app.domain.alignment import align_labels, label_anchor
from app.domain.geometry import Point
from app.domain.polygons import polygon_bbox
from app.ingest.types import ExtractedDocument, ExtractedElement


def fuse_rooms(
    raster: ExtractedDocument, cad: ExtractedDocument, provenance: dict[str, Any]
) -> ExtractedDocument:
    """Use a same-floor DXF only when shared room numbers establish a reliable fit.

    The raster image is preserved. Every native CAD room is mapped into its page,
    including rooms whose names or numbers OCR missed. Unreliable fits leave the
    raster reading intact and record why the companion was not applied.
    """
    if len(raster.pages) != 1 or len(cad.pages) != 1:
        return replace(raster, meta={**raster.meta, "companion_status": "multiple_pages"})
    page, native = raster.pages[0], cad.pages[0]
    rooms = [
        e for e in native.elements if e.kind == "room" and e.source == "dxf" and e.footprint_mm
    ]
    boxes: dict[str, list[tuple[float, float, float, float]]] = {}
    for el in page.elements:
        if el.kind == "room_number" and el.label and el.bbox:
            boxes.setdefault(el.label, []).append(el.bbox)
    pairs: list[tuple[Point, Point]] = []
    for room in rooms:
        found = boxes.get(str(room.properties.get("number")), [])
        anchor = room.properties.get("number_anchor_px")
        horizontal, vertical = room.properties.get("number_alignment", [0, 0])
        if len(found) == 1 and anchor is not None:
            pairs.append((tuple(anchor), label_anchor(found[0], horizontal, vertical)))
    fit = align_labels(pairs, max(3.0, 0.002 * max(page.width_px, page.height_px)))
    if fit is None:
        return replace(raster, meta={**raster.meta, "companion_status": "alignment_failed"})
    mapped: list[ExtractedElement] = []
    for room in rooms:
        polygon = [fit.apply(tuple(p)) for p in room.properties.get("polygon_px", [])]
        if len(polygon) < 3 or any(
            not (-5 <= x <= page.width_px + 5 and -5 <= y <= page.height_px + 5) for x, y in polygon
        ):
            return replace(raster, meta={**raster.meta, "companion_status": "outside_page"})
        number = room.properties.get("number")
        properties = {**room.properties, "polygon_px": [list(p) for p in polygon],
                      "outline_source": "dxf", "companion": provenance}  # fmt: skip
        mapped.append(
            replace(
                room,
                bbox=polygon_bbox(polygon),
                properties=properties,
                name=f"{room.name or 'room'} {number}" if number else room.name,
            )
        )
    info = {**provenance, "matched_labels": fit.support, "rms_px": round(fit.rms_px, 2),
            "rooms": len(mapped)}  # fmt: skip
    page = replace(
        page,
        elements=[e for e in page.elements if e.kind != "room"] + mapped,
        mm_per_px=native.mm_per_px / fit.scale if native.mm_per_px else page.mm_per_px,
        meta={
            **page.meta,
            "room_outlines": {"dxf": len(mapped)},
            "companion_dxf": info,
            "scale_known": native.mm_per_px is not None,
            "scale_method": "companion_dxf",
        },
    )
    return replace(
        raster,
        pages=[page],
        meta={**raster.meta, "companion_status": "matched", "companion_dxf": info},
    )
