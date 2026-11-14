"""The agent's `find_elements` kind filter covers every kind the readers store (#12)."""

from app.domain.ifc_mapping import IFC_KINDS
from app.qa.tools import KINDS, TOOLS, FindIn

# Kinds written by the drawing pipeline: app/domain/tokens.py `classify` plus the
# wall candidates added in app/ingest/annotate.py.
DRAWING_KINDS = {"room", "fixture", "door", "dimension", "scale", "area", "text", "wall"}


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
