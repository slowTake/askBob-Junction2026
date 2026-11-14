"""Answer a recognised question from server-side functions, without the agent loop (#97).

The router says what is asked; the same tools the agent uses do the counting and
adding, so every element used is recorded as evidence and the answer's citations are
checked like any other. Anything that does not fit returns None, and the agent answers.
"""

import json
from typing import Any

from sqlalchemy import select

from app.config import Settings
from app.domain.intents import (
    EXACT_CONFIDENCE,
    Draft,
    Intent,
    RoomRef,
    area_total_draft,
    as_storey,
    count_draft,
    match_room,
    parse_intent,
    quantity_draft,
    reliability,
    room_area_draft,
    tool_request,
)
from app.models import Element
from app.qa.agent import CitationIn, FinalAnswer
from app.qa.router import route
from app.qa.tools import KINDS, QUANTITIES, ToolContext, ToolInputError, run_tool

Found = tuple[Draft, list[dict[str, Any]], tuple[str, dict[str, Any]]]


def fast_events(
    question: str,
    documents: list[dict[str, Any]],
    ctx: ToolContext,
    settings: Settings,
    selected: str | None = None,
) -> list[dict[str, Any]] | None:
    """The events of a server-side answer (`step`, `view`, `final`, as the agent loops
    emit them), or None when the agent should answer.

    Only for one document and no selected element: a count over several drawings, or a
    question about "this room", needs the agent's judgement.
    """
    if settings.fast_path == "off" or selected or len(documents) != 1:
        return None
    raw = route(question, settings, ctx.usage)
    intent = parse_intent(raw, KINDS, QUANTITIES) if raw else None
    if intent is None:
        return None
    found = _try(intent, ctx)
    if found is None and (retry := as_storey(intent)) is not None:
        intent, found = retry, _try(retry, ctx)
    if found is None:
        return None
    draft, elements, step = found
    confidences = [float(e.get("confidence", 0.0)) for e in elements]
    if settings.fast_path == "exact" and min(confidences, default=0.0) < EXACT_CONFIDENCE:
        return None
    events: list[dict[str, Any]] = [{"type": "step", "tool": step[0], "input": step[1]}]
    events += _highlight(elements, draft.answer, ctx)
    confidence, caveat = reliability(confidences)
    answer = FinalAnswer(
        answer=draft.answer,
        value=draft.value,
        unit=draft.unit,
        citations=[
            CitationIn(element_id=e["id"], page_id=None, bbox=None, note=_note(e)) for e in elements
        ],
        confidence=confidence,  # type: ignore[arg-type]  # reliability returns high or medium
        caveats=caveat,
    )
    return [*events, {"type": "final", "answer": answer, "usage": ctx.usage.as_dict()}]


def _try(intent: Intent, ctx: ToolContext) -> Found | None:
    try:
        return _find(intent, ctx)
    except ToolInputError:
        return None


def _find(intent: Intent, ctx: ToolContext) -> Found | None:
    """The answer and the elements it rests on, or None when the data does not settle it."""
    request = tool_request(intent)
    if request is None:
        return _room_area(intent, ctx)
    name, args = request
    data = json.loads(str(run_tool(name, args, ctx)))
    if intent.intent == "count":
        # A count of 0 may mean the reader never found such elements: the agent looks.
        if data["total"] == 0:
            return None
        return count_draft(intent, data["total"]), data["elements"], request
    if intent.intent == "area_total":
        if data["rooms_counted"] == 0:
            return None
        draft = area_total_draft(intent, data["total_m2"], data["rooms_counted"])
        return draft, data["rooms"], request
    if data["elements_summed"] == 0 or data["elements_without_quantity"] > 0:
        return None  # a total over part of the elements is not the total asked for
    return quantity_draft(intent, data["total"], data["elements_summed"]), data["elements"], request


def _room_area(intent: Intent, ctx: ToolContext) -> Found | None:
    room = match_room(rooms(ctx), intent)
    if room is None or room.area_m2 is None:
        return None
    args = {"element_id": room.element_id}
    element = json.loads(str(run_tool("get_element", args, ctx)))
    return room_area_draft(_note(element), room.area_m2), [element], ("get_element", args)


def rooms(ctx: ToolContext) -> list[RoomRef]:
    """Every room in scope, with each way it is written."""
    query = select(Element).where(Element.document_id.in_(ctx.scope), Element.kind == "room")
    return [room_ref(el) for el in ctx.db.scalars(query)]


def room_ref(el: Element) -> RoomRef:
    props = el.properties or {}
    number = props.get("number") or el.label
    plain = [el.text, el.name, el.label, props.get("local_name")]
    # The dataset writes IFC rooms as "LongName (Name)", e.g. "KORIDOR (119)".
    joined = [f"{base} ({el.label})" for base in (el.name, el.text) if base and el.label]
    area = props.get("area_m2")
    return RoomRef(
        str(el.id),
        tuple(dict.fromkeys(str(n) for n in [*plain, *joined] if n)),
        str(number) if number else None,
        props.get("storey"),
        props.get("unit"),
        float(area) if area is not None else None,
    )


def _highlight(
    elements: list[dict[str, Any]], caption: str, ctx: ToolContext
) -> list[dict[str, Any]]:
    """Show the elements on the plan, when they are on one. IFC elements without a
    plan page have nothing to light up."""
    ids = [e["id"] for e in elements if e.get("page_id")]
    if not ids:
        return []
    args = {"element_ids": ids, "caption": caption}
    shown = len(ctx.views)
    try:
        run_tool("highlight", args, ctx)
    except ToolInputError:
        return []
    views = [{"type": "view", "view": view} for view in ctx.views[shown:]]
    return [{"type": "step", "tool": "highlight", "input": args}, *views]


def _note(element: dict[str, Any]) -> str:
    return str(element.get("name") or element.get("label") or element.get("kind") or "element")
