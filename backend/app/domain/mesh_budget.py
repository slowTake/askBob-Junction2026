"""Which 3D meshes to send to the browser when a model is too big to show whole.

Every element stays in the data (questions still count it); only its mesh may be
left out. Building fabric first, then fixtures, then pipes and furniture, then
small parts like fittings and valves.
"""

_TIERS: list[tuple[str, ...]] = [
    ("IfcSpace", "IfcWall", "IfcWallStandardCase", "IfcCurtainWall", "IfcSlab", "IfcRoof",
     "IfcColumn", "IfcBeam", "IfcDoor", "IfcWindow", "IfcStair", "IfcStairFlight",
     "IfcRailing", "IfcPlate", "IfcMember", "IfcCovering", "IfcRamp", "IfcRampFlight"),
    ("IfcSanitaryTerminal", "IfcFlowTerminal", "IfcBuildingElementProxy"),
    ("IfcFurniture", "IfcFurnishingElement", "IfcFlowSegment", "IfcDuctSegment", "IfcPipeSegment"),
]  # fmt: skip
MAX_TRIANGLES = 1_500_000  # roughly 35 MB of JSON, 7 MB gzipped: fine for a browser


def tier(ifc_class: str) -> int:
    for rank, classes in enumerate(_TIERS):
        if ifc_class in classes:
            return rank
    return len(_TIERS)


def within_budget(meshes: list[tuple[str, int]], limit: int = MAX_TRIANGLES) -> list[int]:
    """Indices of (ifc_class, triangle_count) entries to keep, in input order.

    Greedy by tier: take every mesh of the most important tier that still fits,
    then the next tier. A mesh too big to fit is skipped, smaller ones may follow.
    """
    order = sorted(range(len(meshes)), key=lambda i: (tier(meshes[i][0]), i))
    kept: list[int] = []
    used = 0
    for i in order:
        triangles = meshes[i][1]
        if used + triangles <= limit:
            kept.append(i)
            used += triangles
    return sorted(kept)
