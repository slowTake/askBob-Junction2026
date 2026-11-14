"""The question-answering agent on Kimi K3.1 Pro via Verda's OpenAI-compatible API (D-020).

Same tools, prompt, events and answer as the Claude loop in `agent.py`. Differences,
from the #51 capability probe:
- The final answer is a `final_answer` tool call, and every request requires a tool
  call: with a `response_format` schema Kimi skips the tools and invents citations.
- `view_region` images go in a user message after the tool messages (tool messages
  are text-only).
- No adaptive thinking, effort, refusal fallbacks or `cache_control`: Kimi always
  reasons first and Verda caches repeated prefixes on its own.
- The last turn of a run names `final_answer` as the only tool the model may call, so
  a run ends with an answer instead of `too_many_steps` (#95; Kimi and DeepSeek both
  honour a named `tool_choice`).
"""

import os
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

import openai
from pydantic import ValidationError

from app.config import Settings
from app.qa.agent import ANSWER_SCHEMA, MAX_TOKENS, AgentError, FinalAnswer
from app.qa.openai_format import (
    FINAL_TOOL_CHOICE,
    FINAL_TOOL_NOTE,
    Call,
    ToolOutcome,
    assistant_message,
    final_arguments,
    openai_tools,
    parse_arguments,
    tool_messages,
)
from app.qa.prompts import LAST_STEP_NOTE, SYSTEM_PROMPT, scope_message
from app.qa.tools import TOOLS, ToolContext, ToolInputError, run_tool

KEY_ENV = "VERDA_API_KEY"


@lru_cache
def _client(base_url: str, key: str) -> openai.OpenAI:
    return openai.OpenAI(base_url=base_url, api_key=key)


def run_verda_agent(
    question: str,
    documents: list[dict[str, Any]],
    ctx: ToolContext,
    settings: Settings,
    viewing: str | None = None,
    selected: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield `{"type": "step", ...}` per tool call, then one `{"type": "final", ...}`.

    `viewing` and `selected` describe the page on screen and the clicked element.
    """
    # Credentials come from the environment, never from code (D-009).
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        raise AgentError("llm_not_configured")
    client = _client(settings.verda_base_url, key)
    tools = openai_tools(TOOLS, ANSWER_SCHEMA)
    turns = settings.max_agent_turns
    first = scope_message(question, documents, viewing, selected, tool_rounds=turns - 1)
    messages: list[Any] = [
        {"role": "system", "content": SYSTEM_PROMPT + FINAL_TOOL_NOTE},
        {"role": "user", "content": first},
    ]
    usage = {"input_tokens": 0, "output_tokens": 0}

    for turn in range(turns):
        last = turn == turns - 1
        if last and turn > 0:
            messages.append({"role": "user", "content": LAST_STEP_NOTE})
        response = client.chat.completions.create(  # type: ignore[call-overload]  # plain dicts vs SDK TypedDicts
            model=settings.verda_model,
            max_tokens=MAX_TOKENS,  # Kimi's reasoning counts toward this
            messages=messages,
            tools=tools,
            tool_choice=FINAL_TOOL_CHOICE if last else "required",
        )
        if response.usage:
            usage["input_tokens"] += response.usage.prompt_tokens
            usage["output_tokens"] += response.usage.completion_tokens

        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise AgentError("too_long")
        if choice.finish_reason == "content_filter":
            raise AgentError("refused")
        calls = [
            Call(tc.id, tc.function.name, tc.function.arguments)
            for tc in choice.message.tool_calls or []
            if tc.type == "function"
        ]

        final = final_arguments(calls)
        if final is not None:
            try:
                answer = FinalAnswer.model_validate_json(final)
            except ValidationError as exc:
                raise AgentError("bad_answer") from exc
            yield {"type": "final", "answer": answer, "usage": usage}
            return
        if not calls:
            raise AgentError("bad_answer")  # plain text despite tool_choice="required"
        if last:
            break  # other tools instead of the answer: nothing would read their results

        messages.append(assistant_message(choice.message.content, calls))
        outcomes: list[ToolOutcome] = []
        for call in calls:
            try:
                args = parse_arguments(call.arguments)
            except ToolInputError as exc:
                # Every call is a step, as in the Claude loop, even with unreadable input.
                yield {"type": "step", "tool": call.name, "input": {}}
                outcomes.append(ToolOutcome(call.id, str(exc), True))
                continue
            yield {"type": "step", "tool": call.name, "input": args}
            try:
                outcomes.append(ToolOutcome(call.id, run_tool(call.name, args, ctx), False))
            except ToolInputError as exc:
                outcomes.append(ToolOutcome(call.id, str(exc), True))
        messages.extend(tool_messages(outcomes))  # all results in one turn

    raise AgentError("too_many_steps")
