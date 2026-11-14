"""The agent's `find_elements` kind filter covers every kind the readers store (#12)."""

from app.domain.ifc_mapping import IFC_KINDS
from app.domain.kinds import DRAWING_KINDS
from app.qa.tools import KINDS, TOOLS, AreaIn, FindIn


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
