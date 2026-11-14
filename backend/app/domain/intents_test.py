from typing import Any

import pytest

from app.domain.intents import (
    Draft,
    Intent,
    RoomRef,
    area_total_draft,
    as_storey,
    count_draft,
    intent_schema,
    match_room,
    parse_intent,
    quantity_draft,
    reliability,
    room_area_draft,
    tool_request,
)

KINDS = ["room", "unit", "wall", "door", "window", "fixture", "slab"]
QUANTITIES = ["NetVolume", "NetSideArea", "Length"]
EMPTY: dict[str, Any] = {
    "intent": "other", "kind": None, "quantity": None, "subtype": None, "category": None,
    "name": None, "number": None, "unit": None, "storey": None, "refers_to_view": False,
}  # fmt: skip


def _raw(**slots: Any) -> dict[str, Any]:
    return {**EMPTY, **slots}


def _parse(**slots: Any) -> Intent | None:
    return parse_intent(_raw(**slots), KINDS, QUANTITIES)


def test_schema_lists_every_slot_as_required() -> None:
    schema = intent_schema(KINDS, QUANTITIES)
    assert set(schema["required"]) == set(EMPTY)
    assert schema["properties"]["kind"]["anyOf"][0]["enum"] == KINDS
    assert schema["additionalProperties"] is False


# The preview's question patterns, as the router is expected to fill them.
def test_door_count_on_an_ifc_storey() -> None:
    # "How many doors are shown on the floor plan of '4. Sal'?"
    intent = _parse(intent="count", kind="door", storey="4. Sal")
    assert intent == Intent("count", kind="door", storey="4. Sal")
    assert tool_request(intent) == ("count_elements", {
        "kind": "door", "subtype": None, "category": None, "name": None,
        "storey": "4. Sal", "document_id": None, "page_index": None,
    })  # fmt: skip


def test_toilets_are_fixtures_with_a_subtype() -> None:
    # "How many toilet bowls (WC seats) are drawn on this floor plan?"
    intent = _parse(intent="count", kind="fixture", subtype="WC")
    assert intent == Intent("count", kind="fixture", subtype="wc")


def test_rooms_with_a_printed_label() -> None:
    # "Quanti locali con la denominazione «Cucina» ci sono in questo piano?"
    intent = _parse(intent="count", kind="room", name=" Cucina ")
    assert intent == Intent("count", kind="room", name="Cucina")


def test_apartment_area_total() -> None:
    # "What is the net floor area of apartment A in m², summing all its rooms except ...?"
    intent = _parse(intent="area_total", unit="A")
    assert tool_request(intent) == (  # type: ignore[arg-type]
        "sum_room_areas", {"document_id": None, "unit": "A", "name": None},
    )  # fmt: skip


def test_quantity_total_on_a_storey() -> None:
    # "What is the total net volume of all walls on '5. Sal', in m³?"
    intent = _parse(intent="quantity_total", kind="wall", quantity="NetVolume", storey="5. Sal")
    assert tool_request(intent) == ("sum_quantity", {  # type: ignore[arg-type]
        "kind": "wall", "quantity": "NetVolume", "storey": "5. Sal", "document_id": None,
    })  # fmt: skip


def test_one_room_is_not_a_tool_call() -> None:
    # "What is the net floor area of room 1.13 ('Bad') in m²?"
    intent = _parse(intent="room_area", name="Bad", number="1.13")
    assert intent == Intent("room_area", name="Bad", number="1.13")
    assert tool_request(intent) is None


@pytest.mark.parametrize(
    "slots",
    [
        {"intent": "other"},
        {"intent": "where_is"},  # not an intent we know
        {"intent": "count"},  # no kind
        {"intent": "count", "kind": "spaceship"},
        {"intent": "count", "kind": "door", "refers_to_view": True},  # "the doors of this room"
        {"intent": "count", "kind": "fixture", "subtype": "jacuzzi"},
        {"intent": "room_area"},  # neither a name nor a number
        {"intent": "room_area", "name": "  "},
        {"intent": "area_total"},  # neither an apartment nor a label
        {"intent": "quantity_total", "kind": "wall"},  # no quantity
        {"intent": "quantity_total", "kind": "wall", "quantity": "Weight"},
    ],
)
def test_anything_else_goes_to_the_agent(slots: dict[str, Any]) -> None:
    assert _parse(**slots) is None


ROOMS = [
    RoomRef("r1", ("Bad", "room (Bad) 1.13"), "1.13", None, "A", 4.36),
    RoomRef("r2", ("Bad", "room (Bad) 2.07"), "2.07", None, "B", 4.4),
    RoomRef("r3", ("KORIDOR", "119", "KORIDOR (119)"), "119", "1.korrus", None, 63.8),
    RoomRef("r4", ("KORIDOR", "219", "KORIDOR (219)"), "219", "2.korrus", None, 61.2),
]


def test_room_is_found_by_number_and_name() -> None:
    assert match_room(ROOMS, Intent("room_area", name="bad", number="1.13")) == ROOMS[0]
    assert match_room(ROOMS, Intent("room_area", number="2.07")) == ROOMS[1]


def test_room_is_found_by_the_name_and_number_written_together() -> None:
    # "... the room 'KORIDOR (119)' on '1.korrus'"
    found = match_room(ROOMS, Intent("room_area", name="Koridor  (119)", storey="1.KORRUS"))
    assert found == ROOMS[2]


def test_a_storey_tells_two_rooms_of_one_name_apart() -> None:
    assert match_room(ROOMS, Intent("room_area", name="KORIDOR", storey="2.korrus")) == ROOMS[3]


def test_a_storey_does_not_exclude_rooms_that_have_none() -> None:
    # A plan rendered from one storey: its rooms carry no storey name.
    assert match_room(ROOMS, Intent("room_area", number="1.13", storey="4.korrus")) == ROOMS[0]


def test_no_room_or_several_rooms_is_no_match() -> None:
    assert match_room(ROOMS, Intent("room_area", name="Bad")) is None  # r1 and r2
    assert match_room(ROOMS, Intent("room_area", name="Sauna")) is None
    assert match_room(ROOMS, Intent("room_area", name="Bad", number="9.99")) is None


def test_count_wording() -> None:
    assert count_draft(Intent("count", kind="door", storey="3. Sal"), 18) == Draft(
        "18 doors on 3. Sal.", 18.0, "count"
    )
    assert count_draft(Intent("count", kind="unit"), 4).answer == "4 apartments."
    assert count_draft(Intent("count", kind="fixture", subtype="wc"), 2).answer == (
        "2 fixtures (wc)."
    )
    assert count_draft(Intent("count", kind="room", name="Küche"), 1).answer == (
        "1 room labelled 'Küche'."
    )


def test_area_wording() -> None:
    assert room_area_draft("Bad 1.13", 4.36) == Draft("Bad 1.13: 4.36 m².", 4.36, "m2")
    assert area_total_draft(Intent("area_total", unit="A"), 65.1, 5) == Draft(
        "65.1 m² for apartment A (5 rooms).", 65.1, "m2"
    )
    assert area_total_draft(Intent("area_total", name="Balcon"), 12.0, 1).answer == (
        "12 m² for rooms labelled 'Balcon' (1 room)."
    )


def test_quantity_wording_carries_the_unit() -> None:
    intent = Intent("quantity_total", kind="wall", quantity="NetVolume", storey="5. Sal")
    assert quantity_draft(intent, 245.702, 26) == Draft(
        "245.7 m³: NetVolume of all walls on 5. Sal (26 elements).", 245.702, "m3"
    )


def test_exact_sources_are_high_confidence_and_detections_are_not() -> None:
    assert reliability([1.0, 0.95]) == ("high", "")
    confidence, caveat = reliability([1.0, 0.7])  # one door found by the floor-plan model
    assert confidence == "medium" and "not checked" in caveat
    assert reliability([])[0] == "medium"


def test_a_slot_spelt_null_is_empty() -> None:
    # Seen live: the router wrote the string "null" for a number the question lacks.
    intent = _parse(intent="room_area", name="Kontor (Rum nr. 313)", number="null", storey="None")
    assert intent == Intent("room_area", name="Kontor (Rum nr. 313)")


def test_a_name_can_be_read_as_a_storey() -> None:
    intent = Intent("count", kind="door", name="Grundplan")
    assert as_storey(intent) == Intent("count", kind="door", storey="Grundplan")
    # Nothing to move when there is no name, or a storey is already given.
    assert as_storey(Intent("count", kind="door")) is None
    assert as_storey(Intent("count", kind="door", name="A", storey="3. Sal")) is None
    assert as_storey(Intent("room_area", name="Bad")) is None  # a room's name is its name
