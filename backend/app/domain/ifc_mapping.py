"""Map IFC classes and property sets onto our element model."""

from typing import Any

_KINDS = {
    "IfcSpace": "room",
    "IfcWall": "wall",
    "IfcWallStandardCase": "wall",
    "IfcCurtainWall": "wall",
    "IfcDoor": "door",
    "IfcWindow": "window",
    "IfcSlab": "slab",
    "IfcRoof": "roof",
    "IfcColumn": "column",
    "IfcBeam": "beam",
    "IfcStair": "stair",
    "IfcStairFlight": "stair",
    "IfcRailing": "railing",
    "IfcBuildingStorey": "storey",
    "IfcFurnishingElement": "fixture",
    "IfcFurniture": "fixture",
    "IfcSanitaryTerminal": "fixture",
}


def ifc_kind(ifc_class: str) -> str:
    return _KINDS.get(ifc_class, "element")


def flatten_psets(psets: dict[str, dict[str, Any]], limit: int = 60) -> dict[str, Any]:
    """{"Pset_WallCommon": {"IsExternal": True}} -> {"Pset_WallCommon.IsExternal": True}.

    Drops ifcopenshell's internal "id" keys and non-scalar values, keeps at most
    `limit` properties (sorted by key so the result is deterministic).
    """
    flat: dict[str, Any] = {}
    for pset_name in sorted(psets):
        for prop, value in sorted(psets[pset_name].items()):
            if prop == "id" or not isinstance(value, str | int | float | bool):
                continue
            flat[f"{pset_name}.{prop}"] = value
            if len(flat) >= limit:
                return flat
    return flat


def zup_to_yup(verts: list[float], decimals: int = 3) -> list[float]:
    """IFC is Z-up, three.js is Y-up: (x, y, z) -> (x, z, -y), rounded to mm."""
    out: list[float] = []
    for i in range(0, len(verts) - 2, 3):
        x, y, z = verts[i], verts[i + 1], verts[i + 2]
        out.extend((round(x, decimals), round(z, decimals), round(-y, decimals) + 0.0))
    return out
