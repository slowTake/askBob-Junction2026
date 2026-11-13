"""Build an IFC model from what we extracted out of a drawing.

Every product gets a `Bob_Provenance` property set (source document, page, bbox,
confidence), so the BIM model itself says where each wall and room came from.

Units: the file uses millimetres (ifcopenshell's default), and all footprints are
plan millimetres extruded with ShapeBuilder in project units. (Careful:
`ifcopenshell.api.geometry.add_wall_representation` takes metres instead.)
"""

from dataclasses import dataclass, field
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.project
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import numpy as np
from ifcopenshell.util.shape_builder import ShapeBuilder

from app.domain.geometry import Point, polygon_area

PROVENANCE_PSET = "Bob_Provenance"
_CLASSES = {"room": "IfcSpace", "wall": "IfcWall", "door": "IfcDoor", "window": "IfcWindow"}


@dataclass
class BimItem:
    key: str  # caller's element id; returned mapped to the new GlobalId
    kind: str
    label: str | None
    name: str | None
    footprint_mm: list[Point] | None
    value_mm: float | None
    provenance: dict[str, str | float | int] = field(default_factory=dict)


def write_ifc(
    items: list[BimItem],
    out_path: Path,
    project_name: str,
    storey_name: str = "Floor 1",
    height_mm: float = 2600.0,
) -> dict[str, str]:
    """Write the model and return {item.key: GlobalId} for every product created."""
    f = ifcopenshell.api.project.create_file(version="IFC4")
    project = ifcopenshell.api.root.create_entity(f, ifc_class="IfcProject", name=project_name)
    ifcopenshell.api.unit.assign_unit(f)  # millimetres
    model_ctx = ifcopenshell.api.context.add_context(f, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW",
        parent=model_ctx,
    )  # fmt: skip
    storey = _spatial_tree(f, project, storey_name)
    builder = ShapeBuilder(f)

    guids: dict[str, str] = {}
    for item in items:
        ifc_class = _CLASSES.get(item.kind)
        if ifc_class is None:
            continue
        has_shape = item.footprint_mm is not None and polygon_area(item.footprint_mm) > 1.0
        if item.kind in ("room", "wall") and not has_shape:
            continue  # a room or wall without geometry adds nothing to the 3D model

        product = ifcopenshell.api.root.create_entity(
            f, ifc_class=ifc_class, name=item.label or item.kind
        )
        ifcopenshell.api.geometry.edit_object_placement(f, product=product, matrix=np.eye(4))
        if item.kind == "room":
            product.LongName = item.name
        if item.kind in ("door", "window") and item.value_mm:
            product.OverallWidth = float(item.value_mm)
        if has_shape and item.footprint_mm is not None:
            curve = builder.polyline(item.footprint_mm, closed=True)
            solid = builder.extrude(builder.profile(curve), magnitude=height_mm)
            ifcopenshell.api.geometry.assign_representation(
                f, product=product, representation=builder.get_representation(body, [solid])
            )
        if item.kind == "room":
            ifcopenshell.api.aggregate.assign_object(f, products=[product], relating_object=storey)
        else:
            ifcopenshell.api.spatial.assign_container(
                f, products=[product], relating_structure=storey
            )
        pset = ifcopenshell.api.pset.add_pset(f, product=product, name=PROVENANCE_PSET)
        ifcopenshell.api.pset.edit_pset(f, pset=pset, properties=dict(item.provenance))
        guids[item.key] = product.GlobalId

    out_path.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(out_path))
    return guids


def _spatial_tree(
    f: ifcopenshell.file, project: ifcopenshell.entity_instance, storey_name: str
) -> ifcopenshell.entity_instance:
    site = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuilding", name="Building")
    storey = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuildingStorey", name=storey_name)
    ifcopenshell.api.aggregate.assign_object(f, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(f, products=[building], relating_object=site)
    ifcopenshell.api.aggregate.assign_object(f, products=[storey], relating_object=building)
    return storey
