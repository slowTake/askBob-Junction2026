"""Questions the server can answer without the agent loop (#97). Pure.

A small model call fills an `Intent` (what is asked, and the slots the question names);
everything here checks it, turns it into a server-side tool call, and words the answer.
A question that does not fit is `None`: the agent answers it as before.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.domain.quantities import unit_of

ANSWERABLE = ("count", "room_area", "area_total", "quantity_total")
INTENTS = (*ANSWERABLE, "other")
SUBTYPES = ("wc", "washbasin", "sink", "bathtub", "shower")
_TEXT_SLOTS = ("subtype", "category", "name", "number", "unit", "storey")
EXACT_CONFIDENCE = 0.95  # IFC, DXF and PDF text are 1.0; OCR and vision are below this
_SYMBOL = {"m": "m", "m2": "m²", "m3": "m³"}


@dataclass(frozen=True)
class Intent:
    intent: str
    kind: str | None = None
    subtype: str | None = None  # fixtures: wc, washbasin, ...
    category: str | None = None  # rooms of a type: kitchen, sauna, ...
    name: str | None = None  # a printed label, as quoted in the question
    number: str | None = None  # a room number, e.g. "1.13"
    unit: str | None = None  # an apartment, e.g. "A"
    storey: str | None = None
    quantity: str | None = None  # an IFC base quantity, e.g. "NetVolume"


def intent_schema(kinds: Sequence[str], quantities: Sequence[str]) -> dict[str, Any]:
    """JSON schema of the router's output; every property is required, null means absent."""

    def nullable(schema: dict[str, Any]) -> dict[str, Any]:
        return {"anyOf": [schema, {"type": "null"}]}

    properties: dict[str, Any] = {
        "intent": {"type": "string", "enum": list(INTENTS)},
        "kind": nullable({"type": "string", "enum": list(kinds)}),
        "quantity": nullable({"type": "string", "enum": list(quantities)}),
        **{slot: nullable({"type": "string"}) for slot in _TEXT_SLOTS},
        "refers_to_view": {"type": "boolean"},
    }
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}  # fmt: skip


def parse_intent(
    raw: Mapping[str, Any], kinds: Sequence[str], quantities: Sequence[str]
) -> Intent | None:
    """The intent, if the server can answer it; None for anything else.

    None when the router said "other", when the question points at what the user sees
    ("this room"), or when a slot the intent needs is missing or not one we know.
    """
    intent = raw.get("intent")
    if intent not in ANSWERABLE or raw.get("refers_to_view"):
        return None
    slots: dict[str, str | None] = {}
    for slot in (*_TEXT_SLOTS, "kind", "quantity"):
        value = raw.get(slot)
        slots[slot] = value.strip() or None if isinstance(value, str) else None
    kind, quantity, subtype = slots["kind"], slots["quantity"], slots["subtype"]
    if kind is not None and kind not in kinds:
        return None
    if quantity is not None and quantity not in quantities:
        return None
    if subtype is not None:
        slots["subtype"] = subtype = subtype.lower()
        if subtype not in SUBTYPES:
            return None
    if slots["category"] is not None:
        slots["category"] = slots["category"].lower()
    needs = {
        "count": kind is not None,
        "room_area": slots["name"] is not None or slots["number"] is not None,
        "area_total": slots["unit"] is not None or slots["name"] is not None,
        "quantity_total": kind is not None and quantity is not None,
    }
    return Intent(str(intent), **slots) if needs[str(intent)] else None


def tool_request(intent: Intent) -> tuple[str, dict[str, Any]] | None:
    """The agent tool that answers the intent, and its input. None for `room_area`,
    which is one room looked up by `match_room`."""
    if intent.intent == "count":
        return "count_elements", {
            "kind": intent.kind, "subtype": intent.subtype, "category": intent.category,
            "name": intent.name, "storey": intent.storey, "document_id": None,
            "page_index": None,
        }  # fmt: skip
    if intent.intent == "area_total":
        return "sum_room_areas", {"document_id": None, "unit": intent.unit, "name": intent.name}
    if intent.intent == "quantity_total":
        return "sum_quantity", {"kind": intent.kind, "quantity": intent.quantity,
                                "storey": intent.storey, "document_id": None}  # fmt: skip
    return None


@dataclass(frozen=True)
class RoomRef:
    element_id: str
    names: tuple[str, ...]  # every way the room is written: "Bad", "KORIDOR (119)", ...
    number: str | None
    storey: str | None
    unit: str | None
    area_m2: float | None


def _norm(value: str) -> str:
    return " ".join(value.split()).casefold()


def match_room(rooms: Sequence[RoomRef], intent: Intent) -> RoomRef | None:
    """The one room the question names, or None when no room or several rooms fit.

    A name matches any way the room is written, ignoring case and runs of spaces. A
    storey or apartment in the question narrows the choice only among rooms that have
    one: rooms on a drawing have no storey.
    """

    def differs(asked: str | None, actual: str | None) -> bool:
        return asked is not None and actual is not None and _norm(asked) != _norm(actual)

    def fits(room: RoomRef) -> bool:
        if intent.name is not None and _norm(intent.name) not in {_norm(n) for n in room.names}:
            return False
        if intent.number is not None and (
            room.number is None or differs(intent.number, room.number)
        ):
            return False
        return not differs(intent.storey, room.storey) and not differs(intent.unit, room.unit)

    found = [room for room in rooms if fits(room)]
    return found[0] if len(found) == 1 else None


@dataclass(frozen=True)
class Draft:
    answer: str
    value: float
    unit: str


def _number(value: float) -> str:
    return f"{value:g}" if value == int(value) else f"{value:.2f}".rstrip("0").rstrip(".")


def _plural(kind: str | None, count: int = 2) -> str:
    noun = "apartment" if kind == "unit" else str(kind)
    return noun if count == 1 else f"{noun}s"


def count_draft(intent: Intent, total: int) -> Draft:
    if intent.name:
        what = f"{_plural(intent.kind, total)} labelled '{intent.name}'"
    elif intent.subtype or intent.category:
        what = f"{_plural(intent.kind, total)} ({intent.subtype or intent.category})"
    else:
        what = _plural(intent.kind, total)
    where = f" on {intent.storey}" if intent.storey else ""
    return Draft(f"{total} {what}{where}.", float(total), "count")


def room_area_draft(label: str, area_m2: float) -> Draft:
    return Draft(f"{label}: {_number(area_m2)} m².", area_m2, "m2")


def area_total_draft(intent: Intent, total_m2: float, rooms: int) -> Draft:
    if intent.unit and intent.name:
        of = f"rooms labelled '{intent.name}' in apartment {intent.unit}"
    elif intent.unit:
        of = f"apartment {intent.unit}"
    else:
        of = f"rooms labelled '{intent.name}'"
    noun = "room" if rooms == 1 else "rooms"
    return Draft(f"{_number(total_m2)} m² for {of} ({rooms} {noun}).", total_m2, "m2")


def quantity_draft(intent: Intent, total: float, elements: int) -> Draft:
    unit = unit_of(intent.quantity or "") or ""
    where = f" on {intent.storey}" if intent.storey else ""
    noun = "element" if elements == 1 else "elements"
    text = (
        f"{_number(total)} {_SYMBOL.get(unit, unit)}: {intent.quantity} of all "
        f"{_plural(intent.kind)}{where} ({elements} {noun})."
    )
    return Draft(text, total, unit)


def reliability(confidences: Sequence[float]) -> tuple[str, str]:
    """Answer confidence and caveat from the confidence of the elements it rests on."""
    if confidences and min(confidences) >= EXACT_CONFIDENCE:
        return "high", ""
    return "medium", (
        "Read from elements that a detector or OCR found on the drawing; "
        "they were not checked against the drawing for this answer."
    )
