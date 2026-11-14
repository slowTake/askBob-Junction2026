"""Map IFC classes and property sets onto our element model."""

from collections.abc import Mapping
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


OTHER_KIND = "element"
IFC_KINDS = frozenset(_KINDS.values()) | {OTHER_KIND}  # every kind an IFC file can produce


def ifc_kind(ifc_class: str) -> str:
    return _KINDS.get(ifc_class, OTHER_KIND)


UNNAMED_PSET = "Unnamed"


def flatten_psets[K: str | None](
    psets: Mapping[K, Mapping[Any, Any]], limit: int = 60
) -> dict[str, Any]:
    """{"Pset_WallCommon": {"IsExternal": True}} -> {"Pset_WallCommon.IsExternal": True}.

    Drops ifcopenshell's internal "id" keys and non-scalar values, keeps at most
    `limit` properties (sorted by key so the result is deterministic). A set with
    no name (a None key) is kept under UNNAMED_PSET: it often holds quantities.
    """
    named = {UNNAMED_PSET if name is None else name: props for name, props in psets.items()}
    flat: dict[str, Any] = {}
    for pset_name in sorted(named):
        # Properties can be unnamed too (Name is optional in IFC): sort them as text.
        for prop, value in sorted(named[pset_name].items(), key=lambda kv: str(kv[0])):
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


def quantity(psets: Mapping[Any, Mapping[Any, Any]], keys: tuple[str, ...]) -> float | None:
    """First positive value of `keys` found in a quantity set (Qto_* or *Quantities*)."""
    for name, values in psets.items():
        label = str(name) if name is not None else ""
        if not label.startswith("Qto_") and "Quantities" not in label:
            continue
        for key in keys:
            value = values.get(key)
            if isinstance(value, int | float) and value > 0:
                return float(value)
    return None
