"""Pure conversion between our tools/results (Anthropic-shaped) and OpenAI Chat Completions.

Used by the Verda (Kimi) agent loop. Kimi ignores tools when a `response_format` JSON
schema is set (#51 probe), so the final answer is a tool, `final_answer`, whose input
is the answer schema, and every request requires a tool call.
"""

import json
from dataclasses import dataclass
from typing import Any

from app.qa.tools import ToolInputError

FINAL_TOOL = "final_answer"
FINAL_TOOL_NOTE = (
    "\nGive your final answer by calling the `final_answer` tool exactly once, with the "
    "JSON described above as its input. Do not answer in plain text."
)
_IMAGE_NOTE = "The image follows in the next message."


@dataclass(frozen=True)
class Call:
    id: str
    name: str
    arguments: str  # JSON text, as the model sent it


@dataclass(frozen=True)
class ToolOutcome:
    call_id: str
    content: str | list[dict[str, Any]]  # run_tool output, or the error text
    is_error: bool


def _function(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "strict": True,
            "parameters": parameters,
        },
    }


def openai_tools(
    tools: list[dict[str, Any]], answer_schema: dict[str, Any]
) -> list[dict[str, Any]]:
    """Our tool definitions as OpenAI function tools, plus the final-answer tool."""
    out = [_function(t["name"], t["description"], t["input_schema"]) for t in tools]
    out.append(
        _function(
            FINAL_TOOL,
            "Give the final answer with citations. Call this exactly once, as the last step.",
            answer_schema,
        )
    )
    return out


def parse_arguments(raw: str) -> dict[str, Any]:
    """Tool-call arguments must be a JSON object; anything else goes back as a tool error."""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ToolInputError("arguments are not valid JSON") from exc
    if not isinstance(value, dict):
        raise ToolInputError("arguments must be a JSON object")
    return value


def assistant_message(content: str | None, calls: list[Call]) -> dict[str, Any]:
    """The model's tool-call turn, echoed back into the conversation."""
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
            for c in calls
        ],
    }


def final_arguments(calls: list[Call]) -> str | None:
    """Arguments of the final-answer call, if the model made one."""
    return next((c.arguments for c in calls if c.name == FINAL_TOOL), None)


def tool_messages(outcomes: list[ToolOutcome]) -> list[dict[str, Any]]:
    """One tool message per call, then any images in a single user message.

    Tool messages are text-only, and every call must be answered by a tool message right
    after the assistant turn, so images go after the last one.
    """
    messages: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    for outcome in outcomes:
        text, call_images = _split(outcome.content)
        if outcome.is_error:
            text = f"Error: {text}"
        if call_images:
            text = f"{text} {_IMAGE_NOTE}" if text else _IMAGE_NOTE
            images.append({"type": "text", "text": f"Image from tool call {outcome.call_id}:"})
            images.extend(call_images)
        messages.append({"role": "tool", "tool_call_id": outcome.call_id, "content": text})
    if images:
        messages.append({"role": "user", "content": images})
    return messages


def _split(content: str | list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    if isinstance(content, str):
        return content, []
    texts = [b["text"] for b in content if b["type"] == "text"]
    images = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:{b['source']['media_type']};base64,{b['source']['data']}"},
        }
        for b in content
        if b["type"] == "image"
    ]
    return " ".join(texts), images
