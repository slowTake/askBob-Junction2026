"""Flatten DXF entities into plain shapes (millimetre polygons and texts) with a layer role."""

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from ezdxf import path as ezpath

from app.domain.geometry import Point
from app.domain.layers import layer_role

CIRCLE_SEGMENTS = 24


@dataclass
class Shape:
    role: str | None  # from the layer name: wall, door, window, room, unit, text, fixture
    layer: str
    points: list[Point]  # millimetres, y up
    closed: bool
    hatch: bool = False
    kind: str = ""  # DXF entity type, e.g. ARC
    text: str | None = None
    text_height_mm: float = 0.0


def shapes(entities: Any, to_mm: float, layer: str | None = None) -> Iterator[Shape]:
    """Yield shapes for every supported entity; block references are expanded."""
    for e in entities:
        own = e.dxf.get("layer", "0")
        name = layer if layer and own == "0" else own  # entities in blocks inherit layer "0"
        kind = e.dxftype()
        if kind == "INSERT":
            yield from shapes(e.virtual_entities(), to_mm, name)
            continue
        shape = _shape(e, kind, name, to_mm)
        if shape is not None:
            shape.kind = kind
            yield shape


def _shape(e: Any, kind: str, layer: str, to_mm: float) -> Shape | None:
    role = layer_role(layer)

    def mm(points: Any) -> list[Point]:
        return [(float(p[0]) * to_mm, float(p[1]) * to_mm) for p in points]

    if kind in ("TEXT", "MTEXT"):
        text = e.dxf.text if kind == "TEXT" else e.plain_text()
        insert = e.dxf.insert
        height = float(e.dxf.get("height", 0) or e.dxf.get("char_height", 0) or 0)
        return Shape(role, layer, mm([insert]), False, text=" ".join(str(text).split()),
                     text_height_mm=height * to_mm)  # fmt: skip
    if kind == "LWPOLYLINE":
        points = mm(e.get_points("xy"))
        return Shape(role, layer, points, bool(e.closed) or _ends_meet(points))
    if kind == "POLYLINE":
        points = mm(v.dxf.location for v in e.vertices)
        return Shape(role, layer, points, bool(e.is_closed) or _ends_meet(points))
    if kind == "LINE":
        return Shape(role, layer, mm([e.dxf.start, e.dxf.end]), False)
    if kind == "CIRCLE":
        cx, cy, r = e.dxf.center.x, e.dxf.center.y, e.dxf.radius
        ring = [(cx + r * math.cos(2 * math.pi * i / CIRCLE_SEGMENTS),
                 cy + r * math.sin(2 * math.pi * i / CIRCLE_SEGMENTS))
                for i in range(CIRCLE_SEGMENTS)]  # fmt: skip
        return Shape(role, layer, mm(ring), True)
    if kind == "ARC":
        return Shape(role, layer, mm(e.flattening(sagitta=5 / to_mm)), False)
    if kind == "HATCH":
        boundaries = list(ezpath.from_hatch(e))
        if not boundaries:
            return None
        outer = max(boundaries, key=lambda p: len(list(p.control_vertices())))
        points = mm(outer.flattening(distance=10 / to_mm))
        return Shape(role, layer, points, True, hatch=True)
    return None


def _ends_meet(points: list[Point], tolerance_mm: float = 1.0) -> bool:
    return len(points) > 2 and math.dist(points[0], points[-1]) <= tolerance_mm
