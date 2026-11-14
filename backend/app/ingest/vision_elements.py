"""Findings from the floor-plan model (app/domain/vision.py) as stored elements."""

from app.domain.geometry import footprint_mm, polygon_area
from app.domain.polygons import polygon_bbox
from app.domain.vision import Finding, long_side_px
from app.ingest.types import ExtractedElement

SOURCE = "vision"
# Fixture names the agent can search for ("toilet", "washbasin", ...).
_FIXTURE_NAMES = {"wc": "toilet", "washbasin": "washbasin", "sink": "sink", "bathtub": "bathtub"}


def to_element(f: Finding, scale_mm: float | None, page_height: float) -> ExtractedElement:
    properties = {**f.properties, "polygon_px": [list(p) for p in f.polygon]}
    el = ExtractedElement(
        kind=f.kind,
        source=SOURCE,
        name=_name(f),
        bbox=polygon_bbox(f.polygon),
        properties=properties,
        confidence=f.confidence,
    )
    if scale_mm:
        el.footprint_mm = footprint_mm(f.polygon, scale_mm, page_height)
        if f.kind in ("door", "window"):
            el.value_mm = round(long_side_px(f.polygon) * scale_mm, 2)
        if f.kind == "room":
            area = round(polygon_area(f.polygon) * scale_mm * scale_mm / 1e6, 2)
            el.properties["measured_area_m2"] = area
            el.properties["area_m2"] = area
    return el


def _name(f: Finding) -> str | None:
    if f.kind == "room":
        return str(f.properties["category"])
    if f.kind == "fixture":
        subtype = f.properties.get("subtype")
        return _FIXTURE_NAMES.get(str(subtype)) or str(f.properties.get("object", "fixture"))
    return None
