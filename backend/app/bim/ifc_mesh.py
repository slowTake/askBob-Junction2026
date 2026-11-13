"""Triangulate an IFC model into plain JSON meshes for the three.js viewer.

Each mesh keeps its GlobalId, so a citation can highlight the exact element in 3D.
Coordinates are metres, converted to three.js Y-up.
"""

import os
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.geom

from app.domain.ifc_mapping import zup_to_yup

EXCLUDED = ["IfcOpeningElement"]


def ifc_to_mesh(path: Path) -> dict[str, Any]:
    model = ifcopenshell.open(str(path))
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    iterator = ifcopenshell.geom.iterator(
        settings, model, max(1, os.cpu_count() or 1), exclude=EXCLUDED
    )
    meshes: list[dict[str, Any]] = []
    if not iterator.initialize():
        return {"meshes": meshes}
    while True:
        shape = iterator.get()
        element = model.by_id(shape.id)
        if element is None:
            if not iterator.next():
                break
            continue
        meshes.append(
            {
                "guid": shape.guid,
                "ifc_class": element.is_a(),
                "name": getattr(element, "Name", None),
                "positions": zup_to_yup(list(shape.geometry.verts)),
                "indices": list(shape.geometry.faces),
            }
        )
        if not iterator.next():
            break
    return {"meshes": meshes}
