"""Conversion between our Anthropic-shaped tools/results and OpenAI Chat Completions messages.

Expected shapes follow the OpenAI Chat Completions spec, as served by Verda (#51 probe):
function tools under {"type": "function", "function": {...}}, tool results as
{"role": "tool", "tool_call_id", "content": str}, images as image_url data URLs in a user message.
"""

from typing import Any

import pytest

from app.qa.openai_format import (
    FINAL_TOOL,
    Call,
    ToolOutcome,
    assistant_message,
    final_arguments,
    openai_tools,
    parse_arguments,
    tool_messages,
)
from app.qa.tools import ToolInputError

TOOL = {
    "name": "get_element",
    "description": "Get one element.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {"element_id": {"type": "string"}},
        "required": ["element_id"],
        "additionalProperties": False,
    },
}
SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}
IMAGE: dict[str, Any] = {
    "type": "image",
    "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"},
}


def test_tool_becomes_a_strict_function_and_the_final_answer_tool_is_appended() -> None:
    out = openai_tools([TOOL], SCHEMA)
    assert out == [
        {
            "type": "function",
            "function": {
                "name": "get_element",
                "description": "Get one element.",
                "strict": True,
                "parameters": TOOL["input_schema"],
            },
        },
        {
            "type": "function",
            "function": {
                "name": FINAL_TOOL,
                "description": out[1]["function"]["description"],
                "strict": True,
                "parameters": SCHEMA,  # the answer schema is the final tool's input
            },
        },
    ]
    assert FINAL_TOOL == "final_answer"


def test_arguments_are_parsed_as_a_json_object() -> None:
    assert parse_arguments('{"element_id": "e1"}') == {"element_id": "e1"}


@pytest.mark.parametrize("raw", ["", "not json", "[1, 2]", '"text"', "null"])
def test_arguments_that_are_not_a_json_object_are_a_tool_input_error(raw: str) -> None:
    with pytest.raises(ToolInputError):
        parse_arguments(raw)


def test_assistant_message_echoes_the_tool_calls() -> None:
    calls = [Call("c1", "get_element", '{"element_id":"e1"}')]
    assert assistant_message(None, calls) == {
        "role": "assistant",
        "content": "",  # null content is replaced: tool-call turns from Kimi have empty content
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "get_element", "arguments": '{"element_id":"e1"}'},
            }
        ],
    }


def test_final_arguments_found_among_the_calls() -> None:
    calls = [Call("c1", "find_elements", "{}"), Call("c2", FINAL_TOOL, '{"answer":"2"}')]
    assert final_arguments(calls) == '{"answer":"2"}'


def test_no_final_arguments_when_only_ordinary_tools_are_called() -> None:
    assert final_arguments([Call("c1", "find_elements", "{}")]) is None
    assert final_arguments([]) is None


def test_text_results_become_tool_messages_in_call_order() -> None:
    out = tool_messages([ToolOutcome("c1", "[]", False), ToolOutcome("c2", '{"a":1}', False)])
    assert out == [
        {"role": "tool", "tool_call_id": "c1", "content": "[]"},
        {"role": "tool", "tool_call_id": "c2", "content": '{"a":1}'},
    ]


def test_errors_are_marked_in_the_tool_message() -> None:
    # OpenAI tool messages have no is_error flag, so the text says so.
    out = tool_messages([ToolOutcome("c1", "no such page in scope", True)])
    assert out == [
        {"role": "tool", "tool_call_id": "c1", "content": "Error: no such page in scope"}
    ]


def test_images_follow_all_tool_messages_in_one_user_message() -> None:
    # Every tool_call_id must be answered by a tool message straight after the assistant
    # turn, so images can only come after the last tool message.
    region = [IMAGE, {"type": "text", "text": "Page 0 region [0, 0, 10, 10]."}]
    out = tool_messages([ToolOutcome("c1", region, False), ToolOutcome("c2", "[]", False)])
    assert out == [
        {
            "role": "tool",
            "tool_call_id": "c1",
            "content": "Page 0 region [0, 0, 10, 10]. The image follows in the next message.",
        },
        {"role": "tool", "tool_call_id": "c2", "content": "[]"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Image from tool call c1:"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
            ],
        },
    ]


def test_images_from_several_calls_share_one_user_message() -> None:
    out = tool_messages([ToolOutcome("c1", [IMAGE], False), ToolOutcome("c2", [IMAGE], False)])
    assert [m["role"] for m in out] == ["tool", "tool", "user"]
    assert out[0]["content"] == "The image follows in the next message."
    assert [p["type"] for p in out[2]["content"]] == ["text", "image_url", "text", "image_url"]


def test_no_results_give_no_messages() -> None:
    assert tool_messages([]) == []
