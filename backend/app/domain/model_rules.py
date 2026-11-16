"""How an element kind becomes an IFC object, and how an IFC object becomes a kind again.

Both directions live in this one file, so a drawing that goes through IFC comes
back with the same kinds it went in with.
"""

# Kinds with a real IFC class.
_KIND_CLASS = {
    "room": "IfcSpace",
    "wall": "IfcWall",
    "door": "IfcDoor",
    "window": "IfcWindow",
    "unit": "IfcZone",  # an apartment: a group of spaces
    "stair": "IfcStair",
    "column": "IfcColumn",
    "slab": "IfcSlab",
}
# Fixture subtypes with a standard IFC4 IfcSanitaryTerminal type.
_SANITARY = {
    "wc": "TOILETPAN",
    "washbasin": "WASHHANDBASIN",
    "sink": "SINK",
    "shower": "SHOWER",
    "bathtub": "BATH",
}
# Text-like findings (labels, dimensions, scale notes) are 2D annotations.
_ANNOTATION_KINDS = {"text", "dimension", "height", "scale", "area", "room_number"}

BOB_MARK = "bob:"  # ObjectType prefix: "this kind was set by our pipeline"

# (base height, extrusion height) in mm for kinds that get a 3D shape from a footprint.
# Doors become a thin floor marker: a plan tells us where a door is, not its leaf.
_EXTRUSION = {
    "room": (0.0, 2600.0),
    "wall": (0.0, 2600.0),
    "window": (900.0, 1200.0),
    "door": (0.0, 20.0),
    "fixture": (0.0, 450.0),
    "stair": (0.0, 2600.0),
    "column": (0.0, 2600.0),
    "slab": (0.0, 200.0),
}


def ifc_target(kind: str, subtype: str | None = None) -> tuple[str, str | None, str | None]:
    """(IFC class, PredefinedType, ObjectType) for an element kind."""
    if kind == "fixture" and subtype in _SANITARY:
        return "IfcSanitaryTerminal", _SANITARY[subtype], None
    if kind in _KIND_CLASS:
        return _KIND_CLASS[kind], None, None
    if kind in _ANNOTATION_KINDS:
        return "IfcAnnotation", None, BOB_MARK + kind
    return "IfcBuildingElementProxy", None, BOB_MARK + kind


def extrusion_for(kind: str) -> tuple[float, float] | None:
    return _EXTRUSION.get(kind)


def marked_kind(object_type: str | None) -> str | None:
    """The kind our writer stored in ObjectType, if any."""
    if object_type and object_type.startswith(BOB_MARK):
        return object_type[len(BOB_MARK) :] or None
    return None


def sanitary_subtype(predefined_type: str | None) -> str | None:
    """IfcSanitaryTerminal PredefinedType -> our fixture subtype."""
    for subtype, predefined in _SANITARY.items():
        if predefined == predefined_type:
            return subtype
    return None
