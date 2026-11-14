"""The agent's `find_elements` kind filter covers every kind the readers store (#12)."""

import uuid

import pytest
from pydantic import ValidationError

from app.domain.counting import Countable
from app.domain.ifc_mapping import IFC_KINDS
from app.domain.kinds import DRAWING_KINDS
from app.domain.quantities import Measured, unit_of
from app.models import Element
from app.qa.tools import (
    KINDS,
    QUANTITIES,
    TOOLS,
    AreaIn,
    CountIn,
    FindIn,
    QuantityIn,
    countable,
    measured,
    shown_properties,
)


def test_every_ifc_kind_can_be_filtered() -> None:
    assert set(KINDS) >= IFC_KINDS


def test_every_drawing_kind_can_be_filtered() -> None:
    assert set(KINDS) >= DRAWING_KINDS


def test_roof_and_railing_pass_input_validation() -> None:
    # IfcRoof -> "roof" and IfcRailing -> "railing" in app/domain/ifc_mapping.py.
    assert FindIn.model_validate({"kind": "roof"}).kind == "roof"
    assert FindIn.model_validate({"kind": "railing"}).kind == "railing"


def test_tool_schema_offers_the_same_kinds() -> None:
    find = next(t for t in TOOLS if t["name"] == "find_elements")
    enum = find["input_schema"]["properties"]["kind"]["anyOf"][0]["enum"]
    assert enum == KINDS
    assert len(set(KINDS)) == len(KINDS)  # no duplicates in the enum


def test_area_tool_input_is_validated() -> None:
    area = next(t for t in TOOLS if t["name"] == "sum_room_areas")
    assert set(area["input_schema"]["required"]) == {"document_id", "unit", "name"}
    assert AreaIn.model_validate({"document_id": None, "unit": "A", "name": None}).unit == "A"


def test_quantity_tool_names_kinds_and_quantities() -> None:
    tool = next(t for t in TOOLS if t["name"] == "sum_quantity")
    props = tool["input_schema"]["properties"]
    assert tool["strict"] is True
    assert set(tool["input_schema"]["required"]) == {"kind", "quantity", "storey", "document_id"}
    assert props["kind"]["enum"] == KINDS
    assert props["quantity"]["enum"] == QUANTITIES
    # Every quantity on offer has a unit, so the total can always be reported with one.
    assert all(unit_of(q) in ("m", "m2", "m3") for q in QUANTITIES)
    # What the preview's questions ask for: volumes, side areas, floor areas and lengths.
    assert {"NetVolume", "NetSideArea", "NetFloorArea", "Length"} <= set(QUANTITIES)


def test_quantity_tool_input_is_validated() -> None:
    args = QuantityIn.model_validate(
        {"kind": "wall", "quantity": "NetVolume", "storey": "5. Sal", "document_id": None}
    )
    assert (args.kind, args.quantity, args.storey) == ("wall", "NetVolume", "5. Sal")
    with pytest.raises(ValidationError):
        QuantityIn.model_validate({"kind": "wall", "quantity": "Weight"})


def test_measured_reads_storey_and_quantities_from_an_element() -> None:
    el = Element(id=uuid.UUID(int=7), kind="wall",
                 properties={"storey": "1. Sal", "quantities": {"NetVolume": 2.5}})  # fmt: skip
    assert measured(el) == Measured(str(uuid.UUID(int=7)), "wall", "1. Sal", {"NetVolume": 2.5})
    # Elements from drawings, and IFC elements ingested before #96, have no quantities.
    assert measured(Element(id=uuid.UUID(int=8), kind="wall", properties={})).quantities == {}


def test_plan_tools_are_offered_with_strict_inputs() -> None:
    names = {t["name"] for t in TOOLS}
    assert {"highlight", "measure_between"} <= names
    highlight = next(t for t in TOOLS if t["name"] == "highlight")
    assert highlight["strict"] is True
    assert set(highlight["input_schema"]["required"]) == {"element_ids", "caption"}


def test_count_tool_needs_a_kind_and_takes_optional_filters() -> None:
    tool = next(t for t in TOOLS if t["name"] == "count_elements")
    props = tool["input_schema"]["properties"]
    assert set(tool["input_schema"]["required"]) == {
        "kind", "subtype", "category", "name", "storey", "document_id", "page_index",
    }  # fmt: skip
    assert props["kind"]["enum"] == KINDS  # not nullable: a count is always of one kind
    assert CountIn.model_validate(
        {"kind": "door", "subtype": None, "category": None, "name": None,
         "storey": "3. Sal", "document_id": None, "page_index": None}
    ).storey == "3. Sal"  # fmt: skip


def test_count_tool_rejects_a_missing_kind() -> None:
    with pytest.raises(ValidationError):
        CountIn.model_validate({"kind": None})


def test_stored_element_becomes_countable() -> None:
    fixture = Element(
        id=uuid.UUID(int=1), kind="fixture", properties={"subtype": "wc", "storey": "1. Sal"}
    )
    room = Element(
        id=uuid.UUID(int=2), kind="room", label="Küche", text="Küche 2.01",
        properties={"local_name": "Küche", "category": "kitchen"},
    )  # fmt: skip
    assert countable(fixture, None) == Countable(
        str(uuid.UUID(int=1)), "fixture", None, "1. Sal", "wc", None, None
    )
    # The printed label is the room's local name.
    assert countable(room, 0) == Countable(
        str(uuid.UUID(int=2)), "room", 0, None, None, "kitchen", "Küche"
    )


def test_search_results_show_fixture_subtype_and_room_category() -> None:
    # D-022: "how many toilets" is answered from fixtures with subtype "wc"; model
    # rooms carry a category. Layout details (polygon_px) stay out of search results.
    properties = {"subtype": "wc", "category": "bathroom", "area_m2": 4.2, "polygon_px": [[0, 0]]}
    assert shown_properties(properties) == {"subtype": "wc", "category": "bathroom", "area_m2": 4.2}
