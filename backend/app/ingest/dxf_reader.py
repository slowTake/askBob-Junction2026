"""DXF CAD drawings: exact geometry, read by layer meaning (walls, doors, rooms, units).

Everything here comes straight from the CAD file, so confidence is 1.0, apart
from door/window counts, which depend on how their parts are clustered.
"""

import io
from pathlib import Path

import ezdxf
import numpy as np
from PIL import Image

from app.config import Settings
from app.domain.areas import is_shaft, mean_width
from app.domain.geometry import Point, polygon_area
from app.domain.layers import units_to_mm
from app.domain.polygons import (
    cluster_boxes,
    cluster_by_endpoints,
    point_in_polygon,
    polygon_bbox,
)
from app.domain.tokens import Word, classify
from app.ingest.annotate import annotate_page
from app.ingest.dxf_shapes import Shape, shapes
from app.ingest.errors import ReaderError
from app.ingest.render import PageFrame, frame_for, render_png
from app.ingest.types import ExtractedDocument, ExtractedElement, ExtractedPage, Progress

MIN_ROOM_M2 = 0.5
SEMANTIC_ROLES = {"wall", "room", "door", "window", "unit"}
TOUCH_MM = 10.0  # double-door arcs meet at a point
OVERLAP_MM = 1.0  # window/fixture parts overlap by more than this


def read_dxf(path: Path, settings: Settings, progress: Progress) -> ExtractedDocument:
    try:
        doc = ezdxf.readfile(str(path))
    except (OSError, ezdxf.DXFError) as exc:
        raise ReaderError("unreadable_file", "not a readable DXF") from exc
    unit_code = int(doc.header.get("$INSUNITS", 0) or 0)
    to_mm = units_to_mm(unit_code) or 1.0  # unitless files: assume millimetres
    items = list(shapes(doc.modelspace(), to_mm))
    progress("reading", 0.4)

    geometry = [p for s in items if s.text is None for p in s.points]
    if not geometry:
        raise ReaderError("empty_drawing", "DXF has no drawable geometry")
    frame = frame_for(geometry)
    texts = [s for s in items if s.text]
    used_texts: set[int] = set()

    image_png = render_png(items, frame)
    meaningful = any(s.role in SEMANTIC_ROLES for s in items)
    if meaningful:
        units = _areas(items, "unit", texts, used_texts, frame)
        rooms = _areas(items, "room", texts, used_texts, frame)
        for room in rooms:
            _assign_unit(room, units)
        elements = units + rooms + _walls(items, frame)
        for role in ("door", "window", "fixture"):
            elements += _clusters(items, role, frame)
        elements += [_text_element(t, frame) for i, t in enumerate(texts) if i not in used_texts]
    else:
        # Analyse a rendering without text: glyph strokes would look like walls, and
        # the DXF gives us the text exactly anyway.
        geometry_png = render_png([s for s in items if not s.text], frame)
        elements = _by_vision(geometry_png, texts, frame)
    progress("rendering", 0.8)

    page = ExtractedPage(
        index=0,
        image_png=image_png,
        width_px=frame.width_px,
        height_px=frame.height_px,
        dpi=None,
        mm_per_px=1 / frame.px_per_mm,
        elements=elements,
        meta={
            "source": "dxf",
            "units_code": unit_code,
            "units_assumed": units_to_mm(unit_code) is None,
            "layers_meaningful": meaningful,
        },
    )
    layers = sorted({s.layer for s in items})
    return ExtractedDocument(pages=[page], meta={"page_count": 1, "layers": layers})


def _areas(
    items: list[Shape], role: str, texts: list[Shape], used: set[int], frame: PageFrame
) -> list[ExtractedElement]:
    """Closed outlines on room/unit layers, labelled by the texts inside them."""
    out: list[ExtractedElement] = []
    # On room/unit layers every outline encloses an area, even when the CAD
    # "closed" flag is missing (about 40% of the dataset's room outlines).
    outlines = [s for s in items if s.role == role and s.text is None and len(s.points) > 2]
    for outline in outlines:
        area_m2 = polygon_area(outline.points) / 1e6
        if area_m2 < MIN_ROOM_M2:
            continue
        el = ExtractedElement(
            kind=role,
            source="dxf",
            bbox=frame.bbox_px(outline.points),
            footprint_mm=outline.points,
            properties={
                "area_m2": round(area_m2, 2),
                "polygon_px": [
                    [round(x, 1), round(y, 1)] for x, y in map(frame.to_px, outline.points)
                ],
            },
        )
        for i, t in enumerate(texts):
            if i in used or not point_in_polygon(t.points[0], outline.points):
                continue
            if _apply_label(el, t.text or ""):
                used.add(i)
                if classify(t.text or "").kind == "room_number":
                    el.properties["number_anchor_px"] = list(frame.to_px(t.points[0]))
                    el.properties["number_alignment"] = [t.text_halign, t.text_valign]
        if role == "room":
            width_m = mean_width(outline.points) / 1000
            el.properties["shaft"] = is_shaft(el.text, width_m)
        out.append(el)
    return out


def _apply_label(el: ExtractedElement, text: str) -> bool:
    c = classify(text)
    if el.kind == "unit" and c.kind == "unit":
        el.label, el.name = c.label, c.name
    elif el.kind == "room" and c.kind == "room":
        el.text, el.name = text, c.name
        el.label = el.label or c.label
        el.properties.update(c.properties)
    elif el.kind == "room" and c.kind == "room_number":
        el.properties["number"] = c.label
        el.label = c.label if el.label is None or el.label == el.text else el.label
    elif el.kind == "room" and c.kind == "area":
        el.properties["printed_area_m2"] = c.properties["area_m2"]
    else:
        return False
    return True


def _assign_unit(room: ExtractedElement, units: list[ExtractedElement]) -> None:
    if not room.footprint_mm:
        return
    xs = [p[0] for p in room.footprint_mm]
    ys = [p[1] for p in room.footprint_mm]
    centre = (sum(xs) / len(xs), sum(ys) / len(ys))
    for unit in units:
        if unit.footprint_mm and unit.label and point_in_polygon(centre, unit.footprint_mm):
            room.properties["unit"] = unit.label
            return


def _walls(items: list[Shape], frame: PageFrame) -> list[ExtractedElement]:
    walls = [s for s in items if s.role == "wall" and s.closed and len(s.points) > 2]
    if any(s.hatch for s in walls):
        walls = [s for s in walls if s.hatch]  # outlines usually duplicate the hatches
    return [
        ExtractedElement(kind="wall", source="dxf", bbox=frame.bbox_px(s.points),
                         footprint_mm=s.points,
                         properties={"layer": s.layer, "polygon_px": [
                             [round(x, 1), round(y, 1)] for x, y in map(frame.to_px, s.points)
                         ]})
        for s in walls
        if polygon_area(s.points) > 1000  # > 10 cm²
    ]  # fmt: skip


def _clusters(items: list[Shape], role: str, frame: PageFrame) -> list[ExtractedElement]:
    """One element per door/window/fixture, from the CAD parts that make it up.

    Doors: one swing arc per leaf; a double door's two arcs share one endpoint.
    Windows and fixtures: one per closed outline (the open lines inside are glazing
    or detail). Without closed outlines, parts that overlap form one element.
    """
    parts = [s for s in items if s.role == role and s.text is None and s.points]
    if role == "door" and any(s.kind == "ARC" for s in parts):
        parts = [s for s in parts if s.kind == "ARC"]
        groups = cluster_by_endpoints([(s.points[0], s.points[-1]) for s in parts], TOUCH_MM)
    elif any(s.closed for s in parts):
        parts = [s for s in parts if s.closed]  # one frame/outline per window or fixture
        groups = [[i] for i in range(len(parts))]
    else:
        groups = cluster_boxes([polygon_bbox(s.points) for s in parts], -OVERLAP_MM)
    boxes = [polygon_bbox(s.points) for s in parts]
    out: list[ExtractedElement] = []
    for group in groups:
        x0 = min(boxes[i][0] for i in group)
        y0 = min(boxes[i][1] for i in group)
        x1 = max(boxes[i][2] for i in group)
        y1 = max(boxes[i][3] for i in group)
        corners: list[Point] = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        out.append(
            ExtractedElement(
                kind=role,
                source="dxf",
                bbox=frame.bbox_px(corners),
                value_mm=round(max(x1 - x0, y1 - y0)) if role != "fixture" else None,
                properties={"parts": len(group), "layer": parts[group[0]].layer},
                confidence=0.9,
            )
        )
    return out


def _by_vision(geometry_png: bytes, texts: list[Shape], frame: PageFrame) -> list[ExtractedElement]:
    """Layers that say nothing ("0", "Site plan"): analyse the rendered page like a scan,
    but with the DXF's exact text and exact scale."""
    with Image.open(io.BytesIO(geometry_png)) as image:
        gray = np.asarray(image.convert("L"), dtype=np.uint8)
    words = [Word(_text_bbox(t, frame), t.text or "") for t in texts]
    elements, _, _ = annotate_page(gray, words, "dxf", None, known_mm_per_px=1 / frame.px_per_mm)
    return elements


def _text_bbox(t: Shape, frame: PageFrame) -> tuple[float, float, float, float]:
    x, y = frame.to_px(t.points[0])
    size = max(t.text_height_mm * frame.px_per_mm, 8)
    return (x, y - size, x + size * 0.6 * len(t.text or ""), y)


def _text_element(t: Shape, frame: PageFrame) -> ExtractedElement:
    x0, y0, x1, y1 = _text_bbox(t, frame)
    c = classify(t.text or "")
    kind = c.kind if c.kind in ("scale", "dimension") else "text"
    return ExtractedElement(
        kind=kind, source="dxf", text=t.text, label=c.label, value_mm=c.value_mm,
        bbox=(x0, y0, x1, y1), properties={"layer": t.layer},
    )  # fmt: skip
