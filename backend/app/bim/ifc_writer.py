"""Write what a reader extracted from a drawing as an IFC4 model.

Every element becomes an IFC object, text findings included (as IfcAnnotation),
so the IFC is the complete, single result of reading a drawing. Each object
carries a `Bob_Element` property set with its kind, source, confidence, page and
box; `ifc_index.py` reads it back without loss.

Units: the file is in millimetres (ifcopenshell's default) and footprints are
plan millimetres, extruded with ShapeBuilder in project units. (Careful:
`ifcopenshell.api.geometry.add_wall_representation` takes metres instead.)
"""

import json
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.group
import ifcopenshell.api.project
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import numpy as np
from ifcopenshell.util.shape_builder import ShapeBuilder

from app.domain.model_rules import extrusion_for, ifc_target
from app.domain.polygons import clean_polygon
from app.ingest.types import ExtractedElement

BOB_PSET = "Bob_Element"
FOOTPRINT_KEY = "_footprint_mm"  # carried inside the Properties JSON
NAME_MAX = 255


def write_model(
    elements: list[ExtractedElement],
    out_path: Path,
    project_name: str,
    storey_name: str = "Floor 1",
) -> list[str]:
    """Write the model; return each element's GlobalId, in the order given."""
    f = ifcopenshell.api.project.create_file(version="IFC4")
    project = ifcopenshell.api.root.create_entity(f, ifc_class="IfcProject", name=project_name)
    ifcopenshell.api.unit.assign_unit(f)  # millimetres, square metres, cubic metres
    model_ctx = ifcopenshell.api.context.add_context(f, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW",
        parent=model_ctx,
    )  # fmt: skip
    storey = _spatial_tree(f, project, storey_name)
    builder = ShapeBuilder(f)

    guids: list[str] = []
    zones: dict[str, Any] = {}
    spaces_by_unit: dict[str, list[Any]] = {}
    for el in elements:
        product = _product(f, el, storey, body, builder)
        guids.append(product.GlobalId)
        if el.kind == "unit" and el.label:
            zones[el.label] = product
        unit = el.properties.get("unit")
        if el.kind == "room" and isinstance(unit, str):
            spaces_by_unit.setdefault(unit, []).append(product)
    for label, spaces in spaces_by_unit.items():
        if label in zones:
            ifcopenshell.api.group.assign_group(f, products=spaces, group=zones[label])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(out_path))
    return guids


def _product(f: Any, el: ExtractedElement, storey: Any, body: Any, builder: ShapeBuilder) -> Any:
    ifc_class, predefined, object_type = ifc_target(el.kind, el.properties.get("subtype"))
    name = (el.label or el.text or el.kind)[:NAME_MAX]
    product = ifcopenshell.api.root.create_entity(f, ifc_class=ifc_class, name=name)
    if object_type:
        product.ObjectType = object_type
    if predefined:
        product.PredefinedType = predefined

    if ifc_class != "IfcZone":  # zones are groups, not placed objects
        ifcopenshell.api.geometry.edit_object_placement(f, product=product, matrix=np.eye(4))
        if el.kind == "room":
            product.LongName = (el.name or "")[:NAME_MAX] or None
            ifcopenshell.api.aggregate.assign_object(f, products=[product], relating_object=storey)
        else:
            ifcopenshell.api.spatial.assign_container(
                f, products=[product], relating_structure=storey
            )
        if el.kind in ("door", "window") and el.value_mm:
            product.OverallWidth = float(el.value_mm)
        _shape(f, product, el, body, builder)

    _bob_pset(f, product, el)
    area = el.properties.get("area_m2")
    if el.kind == "room" and isinstance(area, int | float) and area > 0:
        qto = ifcopenshell.api.pset.add_qto(f, product=product, name="Qto_SpaceBaseQuantities")
        ifcopenshell.api.pset.edit_qto(f, qto=qto, properties={"NetFloorArea": float(area)})
    return product


def _shape(f: Any, product: Any, el: ExtractedElement, body: Any, builder: ShapeBuilder) -> None:
    extrusion = extrusion_for(el.kind)
    if extrusion is None or not el.footprint_mm:
        return
    outline = clean_polygon(el.footprint_mm, tolerance=1.0)
    if outline is None:
        return
    base, height = extrusion
    profile = builder.profile(builder.polyline(outline, closed=True))
    solid = builder.extrude(profile, magnitude=height, position=(0.0, 0.0, base))
    ifcopenshell.api.geometry.assign_representation(
        f, product=product, representation=builder.get_representation(body, [solid])
    )


def _bob_pset(f: Any, product: Any, el: ExtractedElement) -> None:
    properties = dict(el.properties)
    if el.footprint_mm:
        properties[FOOTPRINT_KEY] = [[round(x, 1), round(y, 1)] for x, y in el.footprint_mm]
    values: dict[str, Any] = {
        "Kind": el.kind,
        "Source": el.source,
        "Confidence": float(el.confidence),
        "Text": el.text,
        "Label": el.label,
        "DisplayName": el.name,
        "ValueMm": float(el.value_mm) if el.value_mm is not None else None,
        "Page": el.page_index,
        "BBoxPx": ",".join(f"{v:.1f}" for v in el.bbox) if el.bbox else None,
        "Properties": json.dumps(properties, ensure_ascii=False, default=str),
    }
    pset = ifcopenshell.api.pset.add_pset(f, product=product, name=BOB_PSET)
    ifcopenshell.api.pset.edit_pset(
        f, pset=pset, properties={k: v for k, v in values.items() if v is not None}
    )


def _spatial_tree(f: Any, project: Any, storey_name: str) -> Any:
    site = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuilding", name="Building")
    storey = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuildingStorey", name=storey_name)
    storey.Elevation = 0.0
    ifcopenshell.api.aggregate.assign_object(f, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(f, products=[building], relating_object=site)
    ifcopenshell.api.aggregate.assign_object(f, products=[storey], relating_object=building)
    return storey
