from copy import deepcopy
from typing import Any

from app.qa.agent import ANSWER_SCHEMA
from app.qa.claude_format import claude_tools
from app.qa.openai_format import openai_tools
from app.qa.plan_tools import PLAN_TOOL_NAMES
from app.qa.tools import TOOLS, AreaIn, CountIn, FindIn


def _unions(value: Any) -> int:
    if isinstance(value, list):
        return sum(_unions(item) for item in value)
    if not isinstance(value, dict):
        return 0
    return int("anyOf" in value or isinstance(value.get("type"), list)) + sum(
        _unions(item) for item in value.values()
    )


def test_complete_request_stays_within_claude_limits_without_losing_tools() -> None:
    tools = claude_tools(TOOLS)
    assert [tool["name"] for tool in tools] == [tool["name"] for tool in TOOLS]
    assert len(tools) == 9  # sum_quantity joined the eight tools (D-037)
    assert _unions(tools) + _unions(ANSWER_SCHEMA) == 5
    optional = sum(
        len(t["input_schema"]["properties"]) - len(t["input_schema"]["required"]) for t in tools
    )
    assert optional == 17 and optional <= 24  # sum_quantity adds optional storey and document_id
    assert all(not t["input_schema"]["additionalProperties"] for t in tools)
    assert all(t["strict"] for t in tools if t["name"] not in PLAN_TOOL_NAMES)


def test_filter_types_and_required_inputs_are_preserved() -> None:
    tools = {t["name"]: t["input_schema"] for t in claude_tools(TOOLS)}
    assert (
        tools["find_elements"]["properties"]["kind"]["enum"]
        == TOOLS[0]["input_schema"]["properties"]["kind"]["anyOf"][0]["enum"]
    )
    assert tools["find_elements"]["required"] == []
    assert tools["count_elements"]["required"] == ["kind"]
    assert tools["highlight"]["required"] == ["element_ids"]
    assert tools["get_element"]["required"] == ["element_id"]
    assert FindIn.model_validate({}).kind is None
    assert AreaIn.model_validate({}).unit is None
    assert CountIn.model_validate({"kind": "door"}).document_id is None


def test_shared_and_verda_schemas_are_not_mutated() -> None:
    before = deepcopy(TOOLS)
    verda = openai_tools(TOOLS, ANSWER_SCHEMA)
    result = claude_tools(TOOLS)
    result[0]["input_schema"]["properties"]["kind"]["enum"].append("changed")
    assert before == TOOLS
    assert openai_tools(TOOLS, ANSWER_SCHEMA) == verda


def test_non_nullable_unions_are_not_changed() -> None:
    tool = {
        "input_schema": {
            "properties": {"x": {"anyOf": [{"type": "string"}, {"type": "integer"}]}},
            "required": ["x"],
        }
    }
    assert claude_tools([tool]) == [tool]
    assert claude_tools([]) == []


def test_plan_tools_are_not_strict_for_claude_and_the_rest_are() -> None:
    # The strict tools and the answer schema compile into one grammar; with every tool
    # strict, Claude rejects the request as too large (400, measured 2026-11-15). The
    # plan tools only draw, and their inputs are validated by the server anyway.
    strict = {t["name"]: t["strict"] for t in claude_tools(TOOLS)}
    assert {name for name, on in strict.items() if not on} == PLAN_TOOL_NAMES
    assert all(t["strict"] for t in TOOLS)  # the shared (Verda) definitions are unchanged
