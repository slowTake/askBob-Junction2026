"""Floor plans for IFC models: one page per storey, drawn from the model's own geometry.

Each element is projected onto the floor (seen from above). Because we draw every
element ourselves, we know exactly where it lands on the page, so IFC elements get
page boxes like drawing elements do: the plan is interactive for every format.
"""

import io
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw
from shapely import MultiPoint, Polygon, unary_union
from shapely.geometry.base import BaseGeometry

from app.domain.geometry import BBox, Point
from app.domain.plan_rules import ROLES, plan_role, space_label
from app.ingest.render import PageFrame, draw_text, frame_for
from app.ingest.types import ExtractedElement, ExtractedPage

MAX_EXACT_TRIANGLES = 3000  # above this, an element's outline is its convex hull
STYLE: dict[str, tuple[Any, Any, int]] = {  # fill, outline, outline width
    "space": ((246, 246, 246), (205, 205, 205), 1),
    "stair": (None, (120, 120, 120), 1),
    "fixture": (None, (110, 110, 110), 1),
    "wall": ((150, 150, 150), (0, 0, 0), 1),
    "column": ((60, 60, 60), (0, 0, 0), 1),
    "window": ((255, 255, 255), (0, 0, 0), 1),
    "door": ((255, 255, 255), (0, 0, 0), 1),
}


@dataclass
class Placed:
    page_index: int
    bbox: BBox
    polygon_px: list[Point]


def floor_plans(
    mesh: dict[str, Any], elements: list[ExtractedElement], storeys: list[dict[str, Any]]
) -> tuple[list[ExtractedPage], dict[str, Placed]]:
    """One page per storey that has drawable elements, and where each element landed."""
    by_guid = {e.ifc_guid: e for e in elements if e.ifc_guid}
    outlines: dict[str, list[tuple[str, ExtractedElement, BaseGeometry]]] = defaultdict(list)
    for m in mesh.get("meshes", []):
        role = plan_role(m["ifc_class"])
        el = by_guid.get(m["guid"])
        if role is None or el is None or not el.properties.get("storey"):
            continue
        shape = _outline(m["positions"], m["indices"])
        if shape is not None and not shape.is_empty:
            outlines[el.properties["storey"]].append((role, el, shape))

    order = [s["name"] for s in sorted(storeys, key=lambda s: s.get("elevation_mm") or 0)]
    order += sorted(name for name in outlines if name not in order)
    pages: list[ExtractedPage] = []
    placed: dict[str, Placed] = {}
    for name in order:
        if not outlines.get(name):
            continue
        page, where = _draw(len(pages), name, outlines[name])
        pages.append(page)
        placed.update(where)
    return pages, placed


def _outline(positions: list[float], indices: list[int]) -> BaseGeometry | None:
    """Top view of a mesh, in plan millimetres (mesh is metres, Y-up: plan = (x, -z))."""
    pts = [(positions[i] * 1000, -positions[i + 2] * 1000) for i in range(0, len(positions), 3)]
    if len(pts) < 3:
        return None
    if len(indices) // 3 > MAX_EXACT_TRIANGLES:
        return MultiPoint(pts).convex_hull
    triangles = []
    for t in range(0, len(indices) - 2, 3):
        tri = Polygon([pts[indices[t]], pts[indices[t + 1]], pts[indices[t + 2]]])
        if tri.area > 1.0:  # skip vertical faces: they project to a line
            triangles.append(tri)
    if not triangles:
        return MultiPoint(pts).convex_hull
    return unary_union(triangles).simplify(5.0)  # 5 mm tolerance


def _draw(
    index: int, storey: str, items: list[tuple[str, ExtractedElement, BaseGeometry]]
) -> tuple[ExtractedPage, dict[str, Placed]]:
    corners: list[Point] = []
    for _, _, shape in items:
        x0, y0, x1, y1 = shape.bounds
        corners += [(x0, y0), (x1, y1)]
    frame = frame_for(corners)
    image = Image.new("RGB", (frame.width_px, frame.height_px), "white")
    draw = ImageDraw.Draw(image)
    placed: dict[str, Placed] = {}
    for role in ROLES:
        fill, outline, width = STYLE[role]
        for item_role, el, shape in items:
            if item_role != role:
                continue
            rings = _rings(shape, frame)
            for exterior, holes in rings:
                if len(exterior) > 2:
                    draw.polygon(exterior, fill=fill, outline=outline, width=width)
                for hole in holes:
                    if len(hole) > 2:
                        draw.polygon(hole, fill="white", outline=outline, width=width)
            if el.ifc_guid and rings:
                placed[el.ifc_guid] = Placed(index, frame.bbox_px(_corners(shape)), rings[0][0])
    for role, el, shape in items:
        if role == "space":
            _label(draw, el, shape, frame)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    page = ExtractedPage(
        index=index, image_png=buffer.getvalue(), width_px=frame.width_px,
        height_px=frame.height_px, dpi=None, mm_per_px=1 / frame.px_per_mm, elements=[],
        meta={"source": "ifc_plan", "storey": storey},
    )  # fmt: skip
    return page, placed


def _rings(shape: BaseGeometry, frame: PageFrame) -> list[tuple[list[Point], list[list[Point]]]]:
    polygons = list(shape.geoms) if hasattr(shape, "geoms") else [shape]
    out = []
    for p in polygons:
        if isinstance(p, Polygon) and not p.is_empty:
            exterior = [frame.to_px(c) for c in p.exterior.coords]
            holes = [[frame.to_px(c) for c in ring.coords] for ring in p.interiors]
            out.append((exterior, holes))
    return out


def _corners(shape: BaseGeometry) -> list[Point]:
    x0, y0, x1, y1 = shape.bounds
    return [(x0, y0), (x1, y1)]


def _label(
    draw: ImageDraw.ImageDraw, el: ExtractedElement, shape: BaseGeometry, frame: PageFrame
) -> None:
    area = el.properties.get("area_m2") or (shape.area / 1e6 if shape.area else None)
    lines = space_label(el.label, el.name, area)
    if not lines:
        return
    x, y = frame.to_px(shape.representative_point().coords[0])
    size = max(11, min(28, int(math.sqrt(shape.area) * frame.px_per_mm / 9)))
    top = y - (len(lines) - 1) * size * 0.6
    for i, line in enumerate(lines):
        draw_text(draw, (x, top + i * size * 1.2), line, size)
