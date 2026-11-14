"""Read-only tools the agent uses to look at the building model.

Every element a tool returns and every region it shows is recorded as evidence;
the final answer may only cite that evidence (see app/domain/citations.py).
"""

import base64
import io
import json
from typing import Any, Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import func, or_, select

from app.domain.areas import RoomArea, net_area
from app.domain.citations import EvidenceItem, element_evidence
from app.domain.geometry import BBox, distance
from app.domain.quantities import Measured, total_quantity
from app.models import Element, Page
from app.qa.context import ToolContext, ToolInputError, parse_id
from app.qa.plan_tools import PLAN_TOOL_NAMES, PLAN_TOOLS, run_plan_tool
from app.storage import page_image_path

KINDS = ["room", "room_number", "unit", "wall", "door", "window", "dimension", "scale", "area",
         "fixture", "text", "slab", "roof", "column", "beam", "stair", "railing", "storey",
         "element"]  # fmt: skip
# IFC base quantities `sum_quantity` can total; units follow the name (domain/quantities.py).
QUANTITIES = ["NetVolume", "GrossVolume", "NetSideArea", "GrossSideArea", "NetFloorArea",
              "GrossFloorArea", "NetArea", "GrossArea", "Length", "Perimeter"]  # fmt: skip
MAX_RESULTS = 50
VIEW_MAX_SIDE = 1568  # longest image side Claude reads without downscaling
VIEW_MIN_SIDE = 768


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def _tool(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    }


_REGION = {k: {"type": "number"} for k in ("x0", "y0", "x1", "y1")}

TOOLS: list[dict[str, Any]] = [
    _tool(
        "find_elements",
        "Search extracted elements. Call this first for any question about rooms, doors, "
        "walls, dimensions or labels. Filter by kind and/or text (fuzzy match on label, "
        "name and text). Returns ids, bounding boxes, values in mm, source and confidence.",
        {
            "kind": _nullable({"type": "string", "enum": KINDS}),
            "text": _nullable({"type": "string"}),
            "document_id": _nullable({"type": "string"}),
            "page_index": _nullable({"type": "integer"}),
            "limit": _nullable({"type": "integer"}),
        },
    ),
    _tool(
        "get_element",
        "Get every stored property of one element (IFC property sets, room polygon, area).",
        {"element_id": {"type": "string"}},
    ),
    _tool(
        "view_region",
        "Look at a rectangle of a drawing page (page pixel coordinates). Use it to check "
        "OCR or computer-vision results, read what text extraction missed, and see how "
        "things relate. Whatever you see here can be cited by page_id and bbox.",
        {"page_id": {"type": "string"}, **_REGION},
    ),
    _tool(
        "measure_distance",
        "Real-world distance in mm between two points on a page with a known scale. "
        "Points are page pixel coordinates (x0, y0) and (x1, y1).",
        {"page_id": {"type": "string"}, **_REGION},
    ),
    _tool(
        "sum_room_areas",
        "Net floor area in m², computed by the drawing's rules: numbered rooms, excluding "
        "shafts and outdoor spaces (balconies, loggias, terraces). Filter by apartment "
        "(unit, e.g. 'A') and/or by the printed room name (e.g. 'Pièce'; then every room "
        "with that name counts, outdoor too). Call this for any area total instead of "
        "adding areas yourself. Returns the total and each room counted, to cite.",
        {
            "document_id": _nullable({"type": "string"}),
            "unit": _nullable({"type": "string"}),
            "name": _nullable({"type": "string"}),
        },
    ),
    _tool(
        "sum_quantity",
        "Total of one base quantity over the elements of one kind in an IFC model, in SI "
        "units: e.g. the net volume of all walls on a storey, the net side area or length "
        "of all walls, the net floor area of all rooms (spaces) on a storey. Call this for "
        "any such total instead of adding element quantities yourself. Narrow with storey "
        "(the storey's name, e.g. '3. Sal') and document_id. Returns the total with its "
        "unit, how many elements were summed and how many lacked the quantity, totals per "
        "storey, and the elements summed (at most 50 listed), to cite and highlight.",
        {
            "kind": {"type": "string", "enum": KINDS},
            "quantity": {"type": "string", "enum": QUANTITIES},
            "storey": _nullable({"type": "string"}),
            "document_id": _nullable({"type": "string"}),
        },
    ),
    *PLAN_TOOLS,
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FindIn(_Strict):
    kind: Literal[tuple(KINDS)] | None = None  # type: ignore[valid-type]
    text: str | None = None
    document_id: str | None = None
    page_index: int | None = None
    limit: int | None = None


class GetIn(_Strict):
    element_id: str


class AreaIn(_Strict):
    document_id: str | None = None
    unit: str | None = None
    name: str | None = None


class QuantityIn(_Strict):
    kind: Literal[tuple(KINDS)]  # type: ignore[valid-type]
    quantity: Literal[tuple(QUANTITIES)]  # type: ignore[valid-type]
    storey: str | None = None
    document_id: str | None = None


class RegionIn(_Strict):
    page_id: str
    x0: float
    y0: float
    x1: float
    y1: float


def run_tool(name: str, raw: Any, ctx: ToolContext) -> str | list[dict[str, Any]]:
    """Run one tool. Raises ToolInputError for bad input (sent back to Claude as is_error)."""
    try:
        if name == "find_elements":
            return _find(FindIn.model_validate(raw), ctx)
        if name == "get_element":
            return _get(GetIn.model_validate(raw), ctx)
        if name == "view_region":
            return _view(RegionIn.model_validate(raw), ctx)
        if name == "measure_distance":
            return _measure(RegionIn.model_validate(raw), ctx)
        if name == "sum_room_areas":
            return _areas(AreaIn.model_validate(raw), ctx)
        if name == "sum_quantity":
            return _quantity(QuantityIn.model_validate(raw), ctx)
        if name in PLAN_TOOL_NAMES:
            return run_plan_tool(name, raw, ctx)
    except ValidationError as exc:
        raise ToolInputError(f"invalid input: {exc.error_count()} problem(s)") from exc
    raise ToolInputError(f"unknown tool {name}")


def _find(args: FindIn, ctx: ToolContext) -> str:
    haystack = (
        func.coalesce(Element.label, "") + " " + func.coalesce(Element.name, "") + " "
        + func.coalesce(Element.text, "")
    )  # fmt: skip
    query = (
        select(Element, Page.index)
        .outerjoin(Page, Element.page_id == Page.id)
        .where(Element.document_id.in_(ctx.scope))
    )
    if args.kind:
        query = query.where(Element.kind == args.kind)
    if args.document_id:
        query = query.where(Element.document_id == _uuid(args.document_id))
    if args.page_index is not None:
        query = query.where(Page.index == args.page_index)
    if args.text:
        similarity = func.similarity(haystack, args.text)
        query = query.where(or_(haystack.ilike(f"%{args.text}%"), similarity > 0.3))
        query = query.order_by(similarity.desc())
    limit = min(max(args.limit or 25, 1), MAX_RESULTS)
    rows = ctx.db.execute(query.limit(limit)).all()
    return json.dumps([_describe(el, page_index, ctx) for el, page_index in rows])


def _get(args: GetIn, ctx: ToolContext) -> str:
    el = ctx.db.get(Element, _uuid(args.element_id))
    if el is None or el.document_id not in ctx.scope:
        raise ToolInputError("no such element in scope")
    page = ctx.db.get(Page, el.page_id) if el.page_id else None
    return json.dumps(
        {**_describe(el, page.index if page else None, ctx), "properties": el.properties}
    )


def _view(args: RegionIn, ctx: ToolContext) -> list[dict[str, Any]]:
    page = _page(args.page_id, ctx)
    box = _clamp((args.x0, args.y0, args.x1, args.y1), page)
    with Image.open(page_image_path(page.document_id, page.index)) as img:
        crop = img.crop((int(box[0]), int(box[1]), int(box[2]), int(box[3])))
    side = max(crop.size)
    if side < VIEW_MIN_SIDE or side > VIEW_MAX_SIDE:
        factor = (VIEW_MIN_SIDE if side < VIEW_MIN_SIDE else VIEW_MAX_SIDE) / side
        crop = crop.resize(
            (max(1, round(crop.width * factor)), max(1, round(crop.height * factor)))
        )
    buffer = io.BytesIO()
    crop.convert("RGB").save(buffer, format="PNG")
    ctx.regions.append(
        EvidenceItem(None, str(page.document_id), str(page.id), page.index, box, None, "region")
    )
    scale = f"{page.mm_per_px:.3f} mm per page pixel" if page.mm_per_px else "scale unknown"
    note = f"Page {page.index} region {[round(v) for v in box]} ({scale})."
    return [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                      "data": base64.b64encode(buffer.getvalue()).decode()}},
        {"type": "text", "text": note},
    ]  # fmt: skip


def _measure(args: RegionIn, ctx: ToolContext) -> str:
    page = _page(args.page_id, ctx)
    if page.mm_per_px is None:
        raise ToolInputError("this page has no known scale; use printed dimensions instead")
    px = distance((args.x0, args.y0), (args.x1, args.y1))
    box = (
        min(args.x0, args.x1),
        min(args.y0, args.y1),
        max(args.x0, args.x1),
        max(args.y0, args.y1),
    )
    ctx.regions.append(
        EvidenceItem(None, str(page.document_id), str(page.id), page.index, box, None, "region")
    )
    return json.dumps({"distance_mm": round(px * page.mm_per_px), "distance_px": round(px, 1)})


def _areas(args: AreaIn, ctx: ToolContext) -> str:
    query = (
        select(Element, Page.index)
        .outerjoin(Page, Element.page_id == Page.id)
        .where(Element.document_id.in_(ctx.scope), Element.kind == "room")
    )
    if args.document_id:
        query = query.where(Element.document_id == _uuid(args.document_id))
    rows = ctx.db.execute(query).all()
    by_id = {str(el.id): (el, page_index) for el, page_index in rows}
    rooms = [
        RoomArea(str(el.id), el.properties.get("number"), el.text, el.properties.get("unit"),
                 float(el.properties["area_m2"]), bool(el.properties.get("outdoor")),
                 bool(el.properties.get("shaft")))
        for el, _ in rows
        if el.properties.get("area_m2") is not None
    ]  # fmt: skip
    total, counted = net_area(rooms, unit=args.unit, name=args.name)
    listed = [_describe(*by_id[r.element_id], ctx) for r in counted]
    return json.dumps({"total_m2": total, "rooms_counted": len(counted), "rooms": listed})


def measured(el: Element) -> Measured:
    """What a quantity total reads from an element: its storey and SI quantities."""
    props = el.properties or {}
    return Measured(str(el.id), el.kind, props.get("storey"), props.get("quantities") or {})


def _quantity(args: QuantityIn, ctx: ToolContext) -> str:
    query = (
        select(Element, Page.index)
        .outerjoin(Page, Element.page_id == Page.id)
        .where(Element.document_id.in_(ctx.scope), Element.kind == args.kind)
    )
    if args.document_id:
        query = query.where(Element.document_id == _uuid(args.document_id))
    rows = ctx.db.execute(query).all()
    by_id = {str(el.id): (el, page_index) for el, page_index in rows}
    items = [measured(el) for el, _ in rows]
    result = total_quantity(
        items, args.kind, args.quantity, storey=args.storey, list_max=MAX_RESULTS
    )
    if args.storey and result.summed + result.missing == 0:
        # A misspelt storey would otherwise read as "the total is 0".
        storeys = sorted({m.storey for m in items if m.storey})
        raise ToolInputError(
            f"no {args.kind} elements on storey {args.storey!r}; storeys with {args.kind} "
            f"elements: {storeys}"
        )
    return json.dumps(
        {
            "total": result.total,
            "unit": result.unit,
            "quantity": args.quantity,
            "elements_summed": result.summed,
            "elements_without_quantity": result.missing,
            "by_storey": result.by_storey,
            "listed": len(result.listed),
            "elements": [
                {**_describe(*by_id[m.element_id], ctx), args.quantity: m.quantities[args.quantity]}
                for m in result.listed
            ],
        }
    )


def _describe(el: Element, page_index: int | None, ctx: ToolContext) -> dict[str, Any]:
    bbox: BBox | None = tuple(el.bbox) if el.bbox else None  # type: ignore[assignment]
    ctx.elements[str(el.id)] = element_evidence(
        str(el.id), str(el.document_id), str(el.page_id) if el.page_id else None,
        page_index, el.kind, bbox, el.properties, el.ifc_guid,
    )  # fmt: skip
    out: dict[str, Any] = {
        "id": str(el.id), "kind": el.kind, "label": el.label, "name": el.name,
        "value_mm": el.value_mm, "document_id": str(el.document_id),
        "page_id": str(el.page_id) if el.page_id else None, "page_index": page_index,
        "bbox": [round(v) for v in el.bbox] if el.bbox else None, "ifc_guid": el.ifc_guid,
        "source": el.source, "confidence": round(el.confidence, 2),
    }  # fmt: skip
    out.update(shown_properties(el.properties))
    return {k: v for k, v in out.items() if v is not None}


# Properties worth showing in every search result. `subtype` (wc, washbasin, ...) and
# `category` come from the floor-plan model too (D-022). get_element shows them all.
_SHOWN = ("area_m2", "number", "unit", "outdoor", "shaft", "subtype", "category")


def shown_properties(properties: dict[str, Any]) -> dict[str, Any]:
    return {key: properties[key] for key in _SHOWN if key in properties}


def _page(page_id: str, ctx: ToolContext) -> Page:
    page = ctx.db.get(Page, _uuid(page_id))
    if page is None or page.document_id not in ctx.scope:
        raise ToolInputError("no such page in scope")
    return page


def _clamp(box: BBox, page: Page) -> BBox:
    x0, x1 = sorted((max(0.0, min(box[0], page.width_px)), max(0.0, min(box[2], page.width_px))))
    y0, y1 = sorted((max(0.0, min(box[1], page.height_px)), max(0.0, min(box[3], page.height_px))))
    if x1 - x0 < 4 or y1 - y0 < 4:
        raise ToolInputError("region is empty after clamping to the page")
    return (x0, y0, x1, y1)


_uuid = parse_id
