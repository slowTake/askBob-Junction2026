"""The question-answering agent: Claude with read-only tools and a structured, cited answer.

A manual tool loop (rather than the SDK's beta tool runner) because we need to:
validate every tool input ourselves, return images from `view_region`, stream each
step to the browser, and record evidence for citation checking.
"""

from collections.abc import Iterator
from functools import lru_cache
from typing import Any, Literal

import anthropic
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.qa.prompts import SYSTEM_PROMPT, scope_message
from app.qa.tools import TOOLS, ToolContext, ToolInputError, run_tool

FALLBACK_BETA = "server-side-fallback-2026-07-01"  # re-run refused requests on a fallback model
MAX_TOKENS = 16_000

_BOX = {
    "type": "object",
    "properties": {k: {"type": "number"} for k in ("x0", "y0", "x1", "y1")},
    "required": ["x0", "y0", "x1", "y1"],
    "additionalProperties": False,
}
_CITATION = {
    "type": "object",
    "properties": {
        "element_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "page_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "bbox": {"anyOf": [_BOX, {"type": "null"}]},
        "note": {"type": "string"},
    },
    "required": ["element_id", "page_id", "bbox", "note"],
    "additionalProperties": False,
}
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": _CITATION},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "caveats": {"type": "string"},
    },
    "required": ["answer", "citations", "confidence", "caveats"],
    "additionalProperties": False,
}


class Box(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class CitationIn(BaseModel):
    element_id: str | None
    page_id: str | None
    bbox: Box | None
    note: str


class FinalAnswer(BaseModel):
    answer: str
    citations: list[CitationIn]
    confidence: Literal["high", "medium", "low"]
    caveats: str


class AgentError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@lru_cache
def _client() -> anthropic.Anthropic:
    # Credentials come from the environment (ANTHROPIC_API_KEY), never from code.
    return anthropic.Anthropic()


def run_agent(
    question: str, documents: list[dict[str, Any]], ctx: ToolContext, settings: Settings
) -> Iterator[dict[str, Any]]:
    """Yield `{"type": "step", ...}` per tool call, then one `{"type": "final", ...}`."""
    client = _client()
    if not (client.api_key or client.auth_token or client.credentials):
        # Without this the SDK raises a bare TypeError on the first request.
        raise AgentError("llm_not_configured")
    messages: list[Any] = [{"role": "user", "content": scope_message(question, documents)}]
    usage = {"input_tokens": 0, "output_tokens": 0}

    for _ in range(settings.max_agent_turns):
        response = client.beta.messages.create(  # type: ignore[call-overload]  # plain dicts vs SDK TypedDicts
            model=settings.claude_model,
            max_tokens=MAX_TOKENS,
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            tools=TOOLS,
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={
                "effort": settings.claude_effort,
                "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
            },
            cache_control={"type": "ephemeral"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        usage["input_tokens"] += response.usage.input_tokens
        usage["output_tokens"] += response.usage.output_tokens

        if response.stop_reason == "refusal":
            raise AgentError("refused")
        if response.stop_reason == "max_tokens":
            raise AgentError("too_long")
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "pause_turn":
            continue

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if tool_uses:
            results: list[dict[str, Any]] = []
            for block in tool_uses:
                yield {"type": "step", "tool": block.name, "input": block.input}
                try:
                    content = run_tool(block.name, block.input, ctx)
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": content}
                    )
                except ToolInputError as exc:
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id,
                         "content": str(exc), "is_error": True}
                    )  # fmt: skip
            messages.append({"role": "user", "content": results})  # all results in one turn
            continue

        text = "".join(b.text for b in response.content if b.type == "text")
        try:
            answer = FinalAnswer.model_validate_json(text)
        except ValidationError as exc:
            raise AgentError("bad_answer") from exc
        yield {"type": "final", "answer": answer, "usage": usage}
        return

    raise AgentError("too_many_steps")
