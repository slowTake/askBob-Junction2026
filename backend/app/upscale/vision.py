"""The one model call of Upscale (#82): look at a page image and say what is missing.

One request per page, no tools and no loop. The provider follows `LLM_PROVIDER`
(D-020): a small Claude model (`UPSCALE_MODEL`) by default, Kimi on Verda otherwise.
The answer is JSON in a fixed schema; `app/domain/upscale.py` decides what is kept.
"""

import base64
import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import anthropic
import openai

from app.config import Settings
from app.domain.upscale import ADDABLE_KINDS

log = logging.getLogger(__name__)

MAX_TOKENS = 12_000  # thinking counts toward it; 120 elements are about 5 000 tokens
MAX_REPORTED = 120
KEY_ENV = "VERDA_API_KEY"

_ELEMENT = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": list(ADDABLE_KINDS)},
        "x0": {"type": "number"},
        "y0": {"type": "number"},
        "x1": {"type": "number"},
        "y1": {"type": "number"},
        "label": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "confidence": {"type": "number"},
    },
    "required": ["kind", "x0", "y0", "x1", "y1", "label", "confidence"],
    "additionalProperties": False,
}
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"elements": {"type": "array", "items": _ELEMENT}},
    "required": ["elements"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = f"""\
You check a floor plan against the elements a program already extracted from it, and \
report the walls, doors, windows and rooms the program missed. Your additions are stored \
and drawn, so a wrong one misleads an engineer: report only what you can clearly see.

You get the page as an image and a JSON list of the elements already known, each with a \
`box` [x0, y0, x1, y1] in pixels of that image (origin top left, y down). Answer in the \
same pixels.

What to report, one entry each:
- `wall`: one box per straight run of wall, as thin as the wall is drawn.
- `door`: a box around the leaf and its swing arc. `label` is the door tag printed at \
it, if any.
- `window`: a box around the window where it sits in the wall.
- `room`: a box around the room's floor, inside its walls. `label` is the room's name \
exactly as printed; skip rooms without a printed name.

Rules:
- Skip anything the list already covers, even when its box is rough. A known room is \
often listed by the box of its printed name only: it is still known.
- Skip title blocks, legends, dimension lines, furniture and hatching.
- `confidence` is between 0 and 1: how sure you are that the element exists there.
- At most {MAX_REPORTED} entries, the clearest first. An empty list is a good answer \
when nothing is missing.
"""


@dataclass(frozen=True)
class Look:
    """What the model answered, before any of it is trusted."""

    data: object  # parsed JSON
    model: str
    input_tokens: int
    output_tokens: int


class VisionError(Exception):
    """The call failed in a way the user can be told about; `code` picks the message."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def user_text(width: int, height: int, listed: list[dict[str, object]], omitted: int) -> str:
    more = f" ({omitted} more are known but not listed.)" if omitted > 0 else ""
    return (
        f"The image is {width} x {height} pixels. Already extracted{more}:\n"
        f"{json.dumps(listed, separators=(',', ':'))}\n"
        "Report what is missing."
    )


def find_missing(
    image_png: bytes,
    width: int,
    height: int,
    listed: list[dict[str, object]],
    omitted: int,
    settings: Settings,
) -> Look:
    """Ask the configured model once. Raises VisionError; never a raw SDK error."""
    text = user_text(width, height, listed, omitted)
    image = base64.b64encode(image_png).decode()
    try:
        if settings.llm_provider == "verda":
            look = _ask_verda(image, text, settings)
        else:
            look = _ask_claude(image, text, settings)
    except (anthropic.AuthenticationError, openai.AuthenticationError):
        log.exception("upscale: llm credentials rejected")
        raise VisionError("llm_not_configured") from None
    except (anthropic.RateLimitError, openai.RateLimitError):
        log.warning("upscale: llm rate limited", exc_info=True)
        raise VisionError("llm_busy") from None
    except (anthropic.APIStatusError, anthropic.APIConnectionError,
            openai.APIStatusError, openai.APIConnectionError):  # fmt: skip
        log.exception("upscale: llm request failed")  # includes timeouts
        raise VisionError("llm_unavailable") from None
    log.info("upscale: %s used %d input and %d output tokens",
             look.model, look.input_tokens, look.output_tokens)  # fmt: skip
    return look


@lru_cache
def _anthropic_client(timeout: float) -> anthropic.Anthropic:
    # Credentials come from the environment (ANTHROPIC_API_KEY), never from code.
    # No retries: the request holds the page's row lock, so it must end within `timeout`.
    return anthropic.Anthropic(timeout=timeout, max_retries=0)


@lru_cache
def _verda_client(base_url: str, key: str, timeout: float) -> openai.OpenAI:
    return openai.OpenAI(base_url=base_url, api_key=key, timeout=timeout, max_retries=0)


def _ask_claude(image: str, text: str, settings: Settings) -> Look:
    client = _anthropic_client(settings.upscale_timeout_s)
    if not (client.api_key or client.auth_token or client.credentials):
        raise VisionError("llm_not_configured")
    response = client.messages.create(
        model=settings.upscale_model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": "image/png", "data": image}},
                    {"type": "text", "text": text},
                ],
            }
        ],
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
        },
    )  # fmt: skip
    if response.stop_reason == "refusal":
        raise VisionError("refused")
    if response.stop_reason == "max_tokens":
        raise VisionError("upscale_failed")  # the JSON is cut off
    # Read by type: the answer can follow thinking blocks.
    answer = "".join(b.text for b in response.content if b.type == "text")
    usage = response.usage
    return Look(_json(answer), settings.upscale_model, usage.input_tokens, usage.output_tokens)


def _ask_verda(image: str, text: str, settings: Settings) -> Look:
    key = os.environ.get(KEY_ENV, "").strip()  # from the keyring, per D-009
    if not key:
        raise VisionError("llm_not_configured")
    client = _verda_client(settings.verda_base_url, key, settings.upscale_timeout_s)
    # No tools: Kimi follows a response_format schema when it is the only constraint (#51).
    response = client.chat.completions.create(
        model=settings.verda_model,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}"}},
                    {"type": "text", "text": text},
                ],
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "missing_elements", "strict": True, "schema": ANSWER_SCHEMA},
        },
    )
    usage = response.usage
    return Look(
        _json(response.choices[0].message.content or ""),
        settings.verda_model,
        usage.prompt_tokens if usage else 0,
        usage.completion_tokens if usage else 0,
    )


def _json(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        raise VisionError("upscale_failed") from None
