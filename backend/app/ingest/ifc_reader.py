"""IFC building models: exact data, no guessing. Provenance is the IFC GlobalId."""

from collections import Counter
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.util.element as ifc_element
import ifcopenshell.util.unit as ifc_unit

from app.config import Settings
from app.domain.ifc_mapping import flatten_psets, ifc_kind
from app.ingest.types import ExtractedDocument, ExtractedElement, Progress

SKIPPED = {"IfcOpeningElement", "IfcVirtualElement", "IfcAnnotation", "IfcGrid", "IfcSite"}
AREA_KEYS = ("NetFloorArea", "GrossFloorArea")


def read_ifc(path: Path, settings: Settings, progress: Progress) -> ExtractedDocument:
    model = ifcopenshell.open(str(path))
    to_mm = ifc_unit.calculate_unit_scale(model) * 1000
    products = [p for p in model.by_type("IfcProduct") if p.is_a() not in SKIPPED]
    elements: list[ExtractedElement] = []
    for i, product in enumerate(products):
        elements.append(_element(product, to_mm))
        if i % 500 == 0:
            progress("reading", i / max(len(products), 1))

    projects = model.by_type("IfcProject")
    meta = {
        "schema": model.schema,
        "project": projects[0].Name if projects else None,
        "counts": dict(Counter(e.kind for e in elements)),
        "length_unit_mm": to_mm,
    }
    return ExtractedDocument(elements=elements, meta=meta)


def _element(product: Any, to_mm: float) -> ExtractedElement:
    ifc_class = product.is_a()
    kind = ifc_kind(ifc_class)
    psets = ifc_element.get_psets(product)
    properties: dict[str, Any] = {"ifc_class": ifc_class, **flatten_psets(psets)}

    storey = ifc_element.get_container(product) or ifc_element.get_aggregate(product)
    if storey is not None and storey.is_a("IfcBuildingStorey"):
        properties["storey"] = storey.Name

    value_mm = None
    for attr in ("OverallWidth", "OverallHeight"):
        raw = getattr(product, attr, None)
        if raw:
            properties[f"{attr}_mm"] = round(float(raw) * to_mm, 1)
    if kind in ("door", "window"):
        value_mm = properties.get("OverallWidth_mm")
    if kind == "storey" and getattr(product, "Elevation", None) is not None:
        value_mm = round(float(product.Elevation) * to_mm, 1)
    if kind == "room":
        for qto in psets.values():
            for key in AREA_KEYS:
                if key in qto and "area_m2" not in properties:
                    properties["area_m2"] = qto[key]

    long_name = getattr(product, "LongName", None)
    return ExtractedElement(
        kind=kind,
        source="ifc",
        text=product.Name,
        label=product.Name,
        name=long_name or product.Name,
        value_mm=value_mm,
        ifc_guid=product.GlobalId,
        properties=properties,
    )
