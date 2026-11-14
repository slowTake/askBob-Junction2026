"""Tools that drive the plan in the browser: highlight elements, measure between two.

Each call appends a view to the context; the agent streams it to the UI as a
`view` event, and the final answer carries all views so a cached answer replays them.
"""

import json
from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.domain.citations import EvidenceItem
from app.domain.geometry import BBox, measure_boxes
from app.models import Element, Page
from app.qa.context import ToolContext, ToolInputError, parse_id

MAX_HIGHLIGHT = 300


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
            }
        ),
    },
    {
        "name": "measure_between",
        "description": "Distance between two elements on the same page (rooms, doors, "
        "fixtures...), centre to centre and between nearest edges, in mm. Draws the "
        "measured line on the plan. Needs a page with a known scale.",
        "strict": True,
        "input_schema": _schema(
            {
                "element_a": {"type": "string"},
                "element_b": {"type": "string"},
            }
        ),
    },
]
PLAN_TOOL_NAMES = {t["name"] for t in PLAN_TOOLS}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HighlightIn(_Strict):
    element_ids: list[str]
    caption: str | None = None


class MeasureIn(_Strict):
    element_a: str
    element_b: str


def run_plan_tool(name: str, raw: Any, ctx: ToolContext) -> str:
    if name == "highlight":
        return _highlight(HighlightIn.model_validate(raw), ctx)
    return _measure(MeasureIn.model_validate(raw), ctx)


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
    ctx.views.append({
        "document_id": str(p.document_id), "page_id": str(p.id), "page_index": p.index,
        "element_ids": [str(el.id) for el, _ in shown], "line": None, "caption": args.caption,
    })  # fmt: skip
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
    ctx.views.append({
        "document_id": str(pa.document_id), "page_id": str(pa.id), "page_index": pa.index,
        "element_ids": [str(a.id), str(b.id)],
        "line": {"from": list(m.start), "to": list(m.end), "label": label}, "caption": None,
    })  # fmt: skip
    return json.dumps({"centre_to_centre_mm": m.centre_mm, "nearest_edges_mm": m.gap_mm,
                       "page_index": pa.index})  # fmt: skip


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
    ctx.elements[str(el.id)] = EvidenceItem(
        str(el.id), str(el.document_id), str(page.id), page.index,
        _box(el) if el.bbox else None, el.ifc_guid,
    )  # fmt: skip
