"""Tools that drive the plan in the browser: highlight, measure between two, route.

Each call appends a view to the context; the agent streams it to the UI as a
`view` event, and the final answer carries all views so a cached answer replays them.
"""

import json
from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.domain.citations import element_evidence
from app.domain.geometry import BBox, measure_boxes
from app.domain.route import Obstacles, find_route, route_length_px, walkable
from app.models import Element, Page
from app.qa.context import ToolContext, ToolInputError, parse_id

MAX_HIGHLIGHT = 300
ROUTE_GRID_CELLS = 600  # the route grid's longer side, whatever the page size
DOOR_PAD_PX = 3  # a door box can be a hair narrower than the wall it opens


def _schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}  # fmt: skip


PLAN_TOOLS: list[dict[str, Any]] = [
    {
        "name": "highlight",
        "description": "Light up elements on the plan the user is looking at. Call this "
        "whenever the answer is about where things are or how many there are ('show the "
        "windows', 'how many bedrooms'), with the ids of the elements concerned. "
        "Elements must be on one page; the page with most of them is shown.",
        "strict": True,
        "input_schema": _schema(
            {
                "element_ids": {"type": "array", "items": {"type": "string"}},
                "caption": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "label": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            }
        ),
    },
    {
        "name": "measure_between",
        "description": "Distance between two elements on the same page (rooms, doors, "
        "fixtures...), centre to centre and between nearest edges, in mm. Draws only the "
        "measured line with its length on the plan (the two elements are not lit up, so "
        "don't also highlight them). Needs a page with a known scale.",
        "strict": True,
        "input_schema": _schema(
            {
                "element_a": {"type": "string"},
                "element_b": {"type": "string"},
            }
        ),
    },
]
PLAN_TOOLS[0]["description"] += (
    " With `label`, that text is written on the plan over the elements: use it for an "
    "area or total about them, e.g. 'Apartment A · 78.4 m²'."
)
PLAN_TOOLS.append(
    {
        "name": "route",
        "description": "Walking route between two elements on the same page, around walls "
        "and through doors, e.g. from an apartment or room to the staircase, an exit door "
        "or the building entrance (find those first with find_elements). Draws the route "
        "with its length on the plan and returns the length in mm (none without a scale).",
        "strict": True,
        "input_schema": _schema(
            {"from_element": {"type": "string"}, "to_element": {"type": "string"}}
        ),
    }
)
PLAN_TOOL_NAMES = {t["name"] for t in PLAN_TOOLS}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HighlightIn(_Strict):
    element_ids: list[str]
    caption: str | None = None
    label: str | None = None


class MeasureIn(_Strict):
    element_a: str
    element_b: str


class RouteIn(_Strict):
    from_element: str
    to_element: str


def run_plan_tool(name: str, raw: Any, ctx: ToolContext) -> str:
    if name == "highlight":
        return _highlight(HighlightIn.model_validate(raw), ctx)
    if name == "route":
        return _route(RouteIn.model_validate(raw), ctx)
    return _measure(MeasureIn.model_validate(raw), ctx)


def _view(page: Page, element_ids: list[str], **extra: Any) -> dict[str, Any]:
    """One plan view; every view has every key, so the UI and the cache see one shape."""
    return {
        "document_id": str(page.document_id), "page_id": str(page.id), "page_index": page.index,
        "element_ids": element_ids, "line": None, "caption": None, "labels": [], "path": None,
        **extra,
    }  # fmt: skip


def _highlight(args: HighlightIn, ctx: ToolContext) -> str:
    ids = [parse_id(i) for i in args.element_ids[:MAX_HIGHLIGHT]]
    if not ids:
        raise ToolInputError("give at least one element id")
    rows = ctx.db.execute(
        select(Element, Page).join(Page, Element.page_id == Page.id)
        .where(Element.id.in_(ids), Element.document_id.in_(ctx.scope))
    ).all()  # fmt: skip
    if not rows:
        raise ToolInputError("none of these elements is on a plan page in scope")
    page = Counter(p.id for _, p in rows).most_common(1)[0][0]
    shown = [(el, p) for el, p in rows if p.id == page]
    for el, p in shown:
        _evidence(el, p, ctx)
    p = shown[0][1]
    labels = []
    if args.label:
        x0, y0, x1, y1 = _union([_extent(el) for el, _ in shown])
        labels = [{"at": [(x0 + x1) / 2, (y0 + y1) / 2], "text": args.label}]
    shown_ids = [str(el.id) for el, _ in shown]
    ctx.views.append(_view(p, shown_ids, caption=args.caption, labels=labels))
    return json.dumps({"highlighted": len(shown), "page_index": p.index,
                       "not_shown": len(args.element_ids) - len(shown)})  # fmt: skip


def _measure(args: MeasureIn, ctx: ToolContext) -> str:
    a, pa = _placed(args.element_a, ctx)
    b, pb = _placed(args.element_b, ctx)
    if pa.id != pb.id:
        raise ToolInputError("the two elements are on different pages")
    if pa.mm_per_px is None:
        raise ToolInputError("this page has no known scale; use printed dimensions instead")
    m = measure_boxes(_box(a), _box(b), pa.mm_per_px)
    for el in (a, b):
        _evidence(el, pa, ctx)
    label = f"{m.centre_mm / 1000:.2f} m"
    line = {"from": list(m.start), "to": list(m.end), "label": label}
    ctx.views.append(_view(pa, [], line=line))  # the line alone: no highlight over it
    return json.dumps({"centre_to_centre_mm": m.centre_mm, "nearest_edges_mm": m.gap_mm,
                       "page_index": pa.index})  # fmt: skip


def _route(args: RouteIn, ctx: ToolContext) -> str:
    a, page = _placed(args.from_element, ctx)
    b, pb = _placed(args.to_element, ctx)
    if page.id != pb.id:
        raise ToolInputError("the two elements are on different pages")
    walls, polygons, doors = [], [], []
    for el in ctx.db.scalars(
        select(Element).where(Element.page_id == page.id, Element.kind.in_(["wall", "door"]))
    ):
        if not el.bbox:
            continue
        if el.kind == "door":
            x0, y0, x1, y1 = _box(el)
            doors.append((x0 - DOOR_PAD_PX, y0 - DOOR_PAD_PX, x1 + DOOR_PAD_PX, y1 + DOOR_PAD_PX))
        elif outline := _outline(el):
            polygons.append([(float(x), float(y)) for x, y in outline])
        else:
            walls.append(_box(el))
    cell = max(1, round(max(page.width_px, page.height_px) / ROUTE_GRID_CELLS))
    free = walkable((page.width_px, page.height_px), Obstacles(walls, polygons, doors), cell)
    points = find_route(free, _centre(_extent(a)), _centre(_extent(b)), cell)
    if points is None:
        raise ToolInputError("no way through: walls separate these two (no door found)")
    for el in (a, b):
        _evidence(el, page, ctx)
    length_mm = route_length_px(points) * page.mm_per_px if page.mm_per_px else None
    label = f"{length_mm / 1000:.1f} m" if length_mm is not None else "route"
    path = {"points": [[round(x, 1), round(y, 1)] for x, y in points], "label": label}
    ctx.views.append(_view(page, [], path=path))
    return json.dumps({"length_mm": round(length_mm) if length_mm is not None else None,
                       "turns": len(points) - 2, "page_index": page.index})  # fmt: skip


def _outline(el: Element) -> list[list[float]] | None:
    polygon = (el.properties or {}).get("polygon_px")
    return polygon if isinstance(polygon, list) and len(polygon) >= 3 else None


def _extent(el: Element) -> BBox:
    """An element's outline bounds when it has one (rooms), else its box."""
    polygon = _outline(el)
    if polygon:
        xs, ys = [float(p[0]) for p in polygon], [float(p[1]) for p in polygon]
        return (min(xs), min(ys), max(xs), max(ys))
    return _box(el)


def _union(boxes: list[BBox]) -> BBox:
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))  # fmt: skip


def _centre(box: BBox) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _placed(element_id: str, ctx: ToolContext) -> tuple[Element, Page]:
    el = ctx.db.get(Element, parse_id(element_id))
    if el is None or el.document_id not in ctx.scope:
        raise ToolInputError("no such element in scope")
    page = ctx.db.get(Page, el.page_id) if el.page_id else None
    if page is None or not el.bbox:
        raise ToolInputError("this element is not on a plan page")
    return el, page


def _box(el: Element) -> BBox:
    x0, y0, x1, y1 = el.bbox or (0, 0, 0, 0)
    return (float(x0), float(y0), float(x1), float(y1))


def _evidence(el: Element, page: Page, ctx: ToolContext) -> None:
    """Shown elements count as evidence, so the answer may cite them."""
    ctx.elements[str(el.id)] = element_evidence(
        str(el.id), str(el.document_id), str(page.id), page.index,
        el.kind, _box(el) if el.bbox else None, el.properties, el.ifc_guid,
    )  # fmt: skip
