"""The agent's `find_elements` kind filter covers every kind the readers store (#12)."""

import uuid

import pytest
from pydantic import ValidationError

from app.domain.counting import Countable
from app.domain.ifc_mapping import IFC_KINDS
from app.domain.kinds import DRAWING_KINDS
from app.models import Element
from app.qa.tools import (
    KINDS,
    TOOLS,
    AreaIn,
    CountIn,
    FindIn,
    countable,
    pages_counted,
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
    doc = uuid.UUID(int=9)
    fixture = Element(
        id=uuid.UUID(int=1), document_id=doc, kind="fixture",
        properties={"subtype": "wc", "storey": "1. Sal"},
    )  # fmt: skip
    room = Element(
        id=uuid.UUID(int=2), document_id=doc, kind="room", label="Küche", text="Küche 2.01",
        name="room (Küche) 2.01", properties={"local_name": "Küche", "category": "kitchen"},
    )  # fmt: skip
    space = Element(
        id=uuid.UUID(int=3), document_id=doc, kind="room", label="005", name="Kitchen",
        properties={"storey": "EG"},
    )  # fmt: skip
    assert countable(fixture, None) == Countable(
        str(uuid.UUID(int=1)), "fixture", None, "1. Sal", "wc", None, None, None, str(doc)
    )
    # The printed label is the room's local name.
    assert countable(room, 0) == Countable(
        str(uuid.UUID(int=2)), "room", 0, None, None, "kitchen", "Küche", "room (Küche) 2.01",
        str(doc),
    )  # fmt: skip
    # An IFC space: the label is its number, the name its LongName (bim/ifc_index.py).
    assert countable(space, None) == Countable(
        str(uuid.UUID(int=3)), "room", None, "EG", None, None, "005", "Kitchen", str(doc)
    )


def test_pages_are_reported_per_document() -> None:
    a, b = str(uuid.UUID(int=1)), str(uuid.UUID(int=2))
    assert pages_counted({(b, 0): 13, (a, 1): 2, (a, 0): 42}) == [
        {"document_id": a, "page_index": 0, "count": 42},
        {"document_id": a, "page_index": 1, "count": 2},
        {"document_id": b, "page_index": 0, "count": 13},
    ]


def test_search_results_show_fixture_subtype_and_room_category() -> None:
    # D-022: "how many toilets" is answered from fixtures with subtype "wc"; model
    # rooms carry a category. Layout details (polygon_px) stay out of search results.
    properties = {"subtype": "wc", "category": "bathroom", "area_m2": 4.2, "polygon_px": [[0, 0]]}
    assert shown_properties(properties) == {"subtype": "wc", "category": "bathroom", "area_m2": 4.2}
