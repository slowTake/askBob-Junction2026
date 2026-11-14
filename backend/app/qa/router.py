"""One small model call that says what a question asks for (#97).

It fills the slots of `app.domain.intents.Intent` and answers nothing itself. Any
failure returns None, and the question goes to the agent as before.
"""

import json
import logging
import os
from typing import Any

import anthropic
import openai

from app.config import Settings
from app.domain.intents import intent_schema
from app.domain.usage import Usage
from app.qa import agent, verda_agent
from app.qa.tools import KINDS, QUANTITIES

log = logging.getLogger(__name__)

ROUTE_TOOL = "route"
MAX_TOKENS = 2_000  # the output is about 80 tokens; the rest is room for a model that reasons first

ROUTER_PROMPT = """\
You sort questions about construction drawings and building models. Say whether the \
question is one of four kinds that a database lookup answers, and copy out what it names. \
Do not answer the question. Questions come in any language.

intent:
- count: how many elements of one kind there are (doors, windows, rooms, walls, columns, \
stairs, apartments, toilets, washbasins ...), in the whole drawing or model, on one named \
storey, or with one printed label.
- room_area: the floor area of ONE room, named by its label and/or number.
- area_total: the net floor area of one apartment, or of all rooms with one printed label.
- quantity_total: a total over all elements of one kind in a building model: the net or \
gross volume, the net or gross side area or the length of all walls, slabs ..., or the net \
floor area of all rooms (spaces) on a storey.
- other: everything else. Where something is, distances, widths, text and schedules, \
comparisons, counts with a condition the slots below cannot hold ("doors wider than \
900", "doors listed in the door schedule", "rooms without a window").

Slots, null when the question does not name them:
- kind: apartments, dwellings and residential units are "unit". Toilets, washbasins, \
sinks, bathtubs and showers are "fixture" with a subtype. Rooms and spaces are "room". \
Floors and storeys are "storey".
- subtype: for fixtures only: wc, washbasin, sink, bathtub or shower.
- category: when rooms of a type are counted and no printed label is quoted: kitchen, \
sauna, bathroom, toilet, bedroom, living room, balcony, terrace, storage ... in English, \
lower case.
- name: a printed label or room name quoted in the question, copied exactly, without the \
quotation marks ('Küche', 'TUALETTRUUM (25-3)').
- number: a room number as written ("1.13").
- unit: the apartment's id ("A").
- storey: the storey's name quoted in the question, copied exactly ('3. Sal'). In "the \
floor plan of 'Grundplan'" and "on '4.korrus'" the quoted word is a storey, not a name.
- quantity: for quantity_total only.
- refers_to_view: true when the question points at something instead of naming it \
("this room", "here", "the selected wall"). "This floor plan" and "this drawing" mean \
the whole document: false.
"""


def route(question: str, settings: Settings, usage: Usage) -> dict[str, Any] | None:
    """The router's raw output for a question, or None when it could not be had."""
    schema = intent_schema(KINDS, QUANTITIES)
    try:
        if settings.llm_provider == "verda":
            return _route_verda(question, settings, usage, schema)
        return _route_claude(question, settings, usage, schema)
    except (openai.APIError, anthropic.APIError, json.JSONDecodeError):
        log.warning("router call failed; the agent answers instead", exc_info=True)
        return None


def _route_verda(
    question: str, settings: Settings, usage: Usage, schema: dict[str, Any]
) -> dict[str, Any] | None:
    key = os.environ.get(verda_agent.KEY_ENV, "").strip()
    if not key:
        return None  # the agent reports the missing key
    client = verda_agent._client(settings.verda_base_url, key)
    tool = {
        "type": "function",
        "function": {"name": ROUTE_TOOL, "description": "Report what the question asks for.",
                     "strict": True, "parameters": schema},
    }  # fmt: skip
    response = client.chat.completions.create(  # type: ignore[call-overload]  # plain dicts vs SDK TypedDicts
        model=settings.router_model or settings.verda_model,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user", "content": question},
        ],
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": ROUTE_TOOL}},
    )
    if response.usage:
        details = getattr(response.usage, "prompt_tokens_details", None)
        cached = getattr(details, "cached_tokens", None) or 0
        usage.add(response.usage.prompt_tokens - cached, response.usage.completion_tokens, cached)
    calls = response.choices[0].message.tool_calls or []
    raw = next((c.function.arguments for c in calls if c.function.name == ROUTE_TOOL), None)
    return _as_object(raw)


def _route_claude(
    question: str, settings: Settings, usage: Usage, schema: dict[str, Any]
) -> dict[str, Any] | None:
    client = agent._client()
    if not (client.api_key or client.auth_token or client.credentials):
        return None  # the agent reports the missing credentials
    response = client.beta.messages.create(
        model=settings.router_model or settings.claude_model,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": ROUTER_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": question}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        betas=[agent.FALLBACK_BETA],
        fallbacks="default",
    )
    usage.add(
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", None) or 0,
        cache_write_tokens=getattr(response.usage, "cache_creation_input_tokens", None) or 0,
    )
    if response.stop_reason != "end_turn":
        return None  # refused or cut off: let the agent handle the question
    return _as_object("".join(b.text for b in response.content if b.type == "text"))


def _as_object(raw: str | None) -> dict[str, Any] | None:
    value = json.loads(raw) if raw else None
    return value if isinstance(value, dict) else None
