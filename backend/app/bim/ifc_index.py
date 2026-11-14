"""Turn any IFC model into the elements the app stores. The one index builder.

Works on uploaded IFC files (Revit, ArchiCAD, ...) and on the IFC our writer
produces from drawings, which carry a `Bob_Element` property set that is read
back without loss. Counting rules live here, so they apply to every format:
an object nested inside another object of the same kind (stair risers inside a
stair) is a part, not a separate element.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.util.element as ifc_element
import ifcopenshell.util.unit as ifc_unit

from app.bim.ifc_writer import BOB_PSET, FOOTPRINT_KEY
from app.domain.ifc_mapping import flatten_psets, ifc_kind, quantity
from app.domain.model_rules import marked_kind, sanitary_subtype
from app.domain.quantities import base_quantities
from app.ingest.types import ExtractedElement

SKIPPED = {"IfcOpeningElement", "IfcVirtualElement", "IfcGrid", "IfcSite", "IfcBuilding"}
AREA_KEYS = ("NetFloorArea", "GrossFloorArea", "NetArea", "GrossArea")


def index_ifc(path: Path) -> tuple[list[ExtractedElement], dict[str, Any]]:
    model = ifcopenshell.open(str(path))
    to_mm = _unit_scale(model, "LENGTHUNIT") * 1000
    to_m2 = _unit_scale(model, "AREAUNIT")
    to_m3 = _unit_scale(model, "VOLUMEUNIT")

    elements: list[ExtractedElement] = []
    product: Any
    for product in model.by_type("IfcProduct"):
        if product.is_a() in SKIPPED:
            continue
        psets = ifc_element.get_psets(product)
        if BOB_PSET in psets:
            el = _from_bob(product, psets[BOB_PSET])
        elif product.is_a("IfcAnnotation"):
            continue  # 2D annotations of uploaded models are drawing furniture, not facts
        else:
            el = _from_ifc(product, psets, to_mm, to_m2, to_m3)
        _relations(product, el)
        elements.append(el)
    elements += _zones(model)
    return elements, _meta(model, elements, to_mm)


def _from_bob(product: Any, bob: dict[str, Any]) -> ExtractedElement:
    properties = json.loads(bob.get("Properties") or "{}")
    footprint = properties.pop(FOOTPRINT_KEY, None)
    bbox = bob.get("BBoxPx")
    page = bob.get("Page")
    return ExtractedElement(
        kind=str(bob.get("Kind") or "element"),
        source=str(bob.get("Source") or "derived"),
        text=bob.get("Text"),
        label=bob.get("Label"),
        name=bob.get("DisplayName"),
        value_mm=bob.get("ValueMm"),
        bbox=tuple(float(v) for v in bbox.split(",")) if bbox else None,  # type: ignore[arg-type]
        footprint_mm=[(float(x), float(y)) for x, y in footprint] if footprint else None,
        ifc_guid=product.GlobalId,
        properties=properties,
        confidence=float(bob.get("Confidence", 1.0)),
        page_index=int(page) if page is not None else None,
    )


def _from_ifc(
    product: Any, psets: dict[str, Any], to_mm: float, to_m2: float, to_m3: float
) -> ExtractedElement:
    ifc_class = product.is_a()
    type_obj = ifc_element.get_type(product)
    kind = marked_kind(getattr(product, "ObjectType", None)) or ifc_kind(ifc_class)
    properties: dict[str, Any] = {"ifc_class": ifc_class, **flatten_psets(psets)}
    if type_obj is not None:
        properties["type_name"] = type_obj.Name
        if type_obj.is_a("IfcSanitaryTerminalType"):  # IFC2X3 toilets are IfcFlowTerminals
            kind = "fixture"
    if getattr(product, "ObjectType", None):
        properties["object_type"] = product.ObjectType
    predefined = getattr(product, "PredefinedType", None) or getattr(
        type_obj, "PredefinedType", None
    )
    if kind == "fixture" and (subtype := sanitary_subtype(predefined)):
        properties["subtype"] = subtype

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
        area = quantity(psets, AREA_KEYS)
        if area is not None:
            properties["area_m2"] = round(area * to_m2, 2)

    # Lengths, areas and volumes in SI units, for the agent's `sum_quantity` tool. Kept
    # apart from the flattened property sets, which are capped and in the model's units.
    if quantities := base_quantities(psets, to_mm / 1000, to_m2, to_m3):
        properties["quantities"] = quantities

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


def _relations(product: Any, el: ExtractedElement) -> None:
    container = ifc_element.get_container(product)
    aggregate = ifc_element.get_aggregate(product)
    storey = container if container is not None else aggregate
    if storey is not None and storey.is_a("IfcBuildingStorey"):
        el.properties.setdefault("storey", storey.Name)
    if aggregate is not None and aggregate.is_a() == product.is_a():
        el.properties["part_of"] = aggregate.GlobalId  # e.g. a riser inside a stair
    for rel in getattr(product, "FillsVoids", None) or ():  # door/window -> its host wall
        host = rel.RelatingOpeningElement.VoidsElements
        if host:
            el.properties["host"] = host[0].RelatingBuildingElement.GlobalId


def _zones(model: Any) -> list[ExtractedElement]:
    """Apartments and other zones: IfcZone groups. Members get `unit` = the zone's name."""
    out: list[ExtractedElement] = []
    for zone in model.by_type("IfcZone"):
        psets = ifc_element.get_psets(zone)
        if BOB_PSET in psets:
            el = _from_bob(zone, psets[BOB_PSET])
        else:
            el = ExtractedElement(kind="unit", source="ifc", text=zone.Name, label=zone.Name,
                                  name=getattr(zone, "LongName", None) or zone.Name,
                                  ifc_guid=zone.GlobalId)  # fmt: skip
        out.append(el)
    return out


def _meta(model: Any, elements: list[ExtractedElement], to_mm: float) -> dict[str, Any]:
    projects = model.by_type("IfcProject")
    header = model.header.file_name
    storeys = [
        {"name": s.Name, "elevation_mm": round(float(s.Elevation or 0) * to_mm, 1)}
        for s in model.by_type("IfcBuildingStorey")
    ]
    top = [e for e in elements if "part_of" not in e.properties]
    return {
        "schema": model.schema,
        "project": projects[0].Name if projects else None,
        "authoring_tool": header.originating_system or None,
        "ifc_preprocessor": header.preprocessor_version or None,
        "author": ", ".join(a for a in header.author if a) or None,
        "storeys": storeys,
        "counts": dict(Counter(e.kind for e in top)),
        "length_unit_mm": to_mm,
    }


def _unit_scale(model: Any, unit_type: str) -> float:
    try:
        return float(ifc_unit.calculate_unit_scale(model, unit_type))
    except Exception:  # files without unit assignments: IFC's default is SI (m, m²)
        return 1.0
