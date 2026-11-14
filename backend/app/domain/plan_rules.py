"""What a floor plan generated from an IFC model shows, and how rooms are labelled."""

# Drawing roles, in drawing order (later roles are drawn on top).
ROLES = ("space", "stair", "fixture", "wall", "column", "window", "door")

_ROLE_BY_CLASS = {
    "IfcSpace": "space",
    "IfcWall": "wall",
    "IfcWallStandardCase": "wall",
    "IfcCurtainWall": "wall",
    "IfcColumn": "column",
    "IfcDoor": "door",
    "IfcWindow": "window",
    "IfcStair": "stair",
    "IfcStairFlight": "stair",
    "IfcRailing": "stair",
    "IfcSanitaryTerminal": "fixture",
    "IfcFlowTerminal": "fixture",
    "IfcFurniture": "fixture",
    "IfcFurnishingElement": "fixture",
}


def plan_role(ifc_class: str) -> str | None:
    """None: not drawn on a floor plan (slabs would cover the whole floor, pipes clutter it)."""
    return _ROLE_BY_CLASS.get(ifc_class)


def space_label(name: str | None, long_name: str | None, area_m2: float | None) -> list[str]:
    """Lines printed in a room: function, number, area ("Kitchen", "B104", "12.4 m²")."""
    lines: list[str] = []
    if long_name and long_name != name:
        lines.append(long_name)
    if name:
        lines.append(name)
    if area_m2:
        lines.append(f"{area_m2:.1f} m²")
    return lines
