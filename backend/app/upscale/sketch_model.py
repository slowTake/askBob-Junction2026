"""The model call of the sketch redraw (#82): draw the plan, or check a draft of it.

Round 1 sends the photo and asks for the whole plan. Each later round sends the photo,
a render of the current draft and the draft's JSON, and asks whether they match; if
not, the model returns the corrected plan. The loop is in `sketch_loop.py`; what the
answer means is decided in `app/domain/sketch*.py`.

Claude only (`SKETCH_MODEL`, a strong model by default): with `LLM_PROVIDER=verda`
the call fails with `sketch_needs_claude` instead of quietly using a weaker model.
"""

import base64
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, cast

import anthropic
from anthropic.types.beta import BetaMessageParam

from app.config import Settings
from app.upscale.vision import Look, VisionError

log = logging.getLogger(__name__)

MAX_TOKENS = 32_000  # streamed; thinking counts toward it, a plan is a few thousand tokens
FALLBACK_BETA = "server-side-fallback-2026-07-01"

_NUMBER = {"type": "number"}
_POINT = {
    "type": "object",
    "properties": {"x": _NUMBER, "y": _NUMBER},
    "required": ["x", "y"],
    "additionalProperties": False,
}
_ENDS = {"x0": _NUMBER, "y0": _NUMBER, "x1": _NUMBER, "y1": _NUMBER}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _list(item: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": item}


PLAN_SCHEMA = _object(
    {
        "matches": {"type": "boolean"},
        "walls": _list(_object({**_ENDS, "outer": {"type": "boolean"}})),
        "doors": _list(
            _object(
                {
                    **_ENDS,
                    "hinge": {"type": "string", "enum": ["start", "end"]},
                    "opens_toward_x": _NUMBER,
                    "opens_toward_y": _NUMBER,
                }
            )
        ),
        "windows": _list(_object(dict(_ENDS))),
        "rooms": _list(
            _object(
                {"name": {"type": "string"}, "x": _NUMBER, "y": _NUMBER, "outline": _list(_POINT)}
            )
        ),
        "texts": _list(_object({"text": {"type": "string"}, "x": _NUMBER, "y": _NUMBER})),
    }
)

SYSTEM_PROMPT = """\
You redraw hand-drawn floor plans (napkin sketches, photographed) as clean floor plans. \
A program draws exactly the plan you return, so the plan must describe what the sketch \
shows: the same walls, doors, windows, rooms and writing, in the same places. Redraw; \
never invent.

Coordinates are pixels of the photo (image 1): origin at the top left, x to the right, \
y down.

What to return:
- `walls`: one entry per straight run of wall, along the middle of the drawn line, from \
one end to the other. A wall runs straight through the doors and windows in it: give \
the whole run, the program cuts the openings. End a run where it meets another wall, so \
corners and T-junctions share an end point. `outer` is true for the building's outside \
walls.
- `doors`: the door opening, where the gap in the wall is, as two points on the wall's \
line. `hinge` says which of the two ends the door leaf is hinged at (the centre of the \
swing arc): "start" for (x0, y0), "end" for (x1, y1). `opens_toward` is any point in \
the room the leaf swings into, for example the middle of the drawn arc.
- `windows`: the stretch of wall where a window is drawn, as two points on the wall's line.
- `rooms`: every room with a written name. `name` exactly as written, same spelling and \
case. (x, y) is the middle of the written name. `outline` is the room's corners along \
the walls, in order; leave it empty when the room has no clear outline.
- `texts`: anything else written on the sketch, exactly as written (a dimension, a note, \
a north arrow's letter), at the middle of the writing. Leave it empty when nothing else \
is written.

Never add anything that is not drawn or written: no dimensions, measurements, areas, \
scale or labels of your own, no furniture, fixtures or hatching. If the sketch has no \
numbers, your plan has no numbers.
"""

CHECK_TEXT = """\
Image 2 is the sketch again with your current draft, drawn by the program from the plan \
below, laid over it in red. Where the draft is right, red covers the drawn line. A drawn \
line with no red on it, or red with no drawn line under it, is an error in the plan.

Check position first: each red wall must lie on the line it stands for, along its whole \
length, and the red outline must be as wide and as tall as the drawn one. If the red \
plan is smaller, larger or shifted against the sketch, read off how far each wall is \
from its line and move it there; do not accept a draft that only has the right layout. \
A hand-drawn line wobbles: a red wall within about one wall thickness of its line is in \
place.
Then check the parts: corners closed where the sketch's corners are, every door and \
window on the right wall at the right spot with the right hinge and swing side, every \
room name right and in its room, and nothing that is not on the sketch (in particular \
no text or number that is not written there).
If the draft matches the sketch, answer with `matches` true and the plan below unchanged. \
Otherwise answer with `matches` false and the whole corrected plan, not just the changes.

Current plan:
"""


@dataclass(frozen=True)
class SketchAsk:
    """One round: the photo as sent, and for a check round the draft and its plan."""

    photo_png: bytes
    width: int
    height: int
    draft_png: bytes | None = None
    draft: dict[str, Any] | None = None
    ink: tuple[int, int, int, int] | None = None  # measured dark-pixel box of the photo


def ask_sketch(ask: SketchAsk, settings: Settings) -> Look:
    """Ask the configured Claude model once. Raises VisionError; never a raw SDK error."""
    if settings.llm_provider != "anthropic":
        raise VisionError("sketch_needs_claude")
    client = _client(settings.sketch_timeout_s)
    if not (client.api_key or client.auth_token or client.credentials):
        raise VisionError("llm_not_configured")
    try:
        with client.beta.messages.stream(
            model=settings.sketch_model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=cast(list[BetaMessageParam], [{"role": "user", "content": content(ask)}]),
            thinking={"type": "adaptive"},
            output_config={
                "effort": settings.sketch_effort,
                "format": {"type": "json_schema", "schema": PLAN_SCHEMA},
            },
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            response = stream.get_final_message()
    except anthropic.AuthenticationError:
        log.exception("sketch: llm credentials rejected")
        raise VisionError("llm_not_configured") from None
    except anthropic.RateLimitError:
        log.warning("sketch: llm rate limited", exc_info=True)
        raise VisionError("llm_busy") from None
    except (anthropic.APIStatusError, anthropic.APIConnectionError):
        log.exception("sketch: llm request failed")  # includes timeouts
        raise VisionError("llm_unavailable") from None

    if response.stop_reason == "refusal":
        raise VisionError("refused")
    if response.stop_reason == "max_tokens":
        raise VisionError("sketch_failed")  # the JSON is cut off
    answer = "".join(b.text for b in response.content if b.type == "text")
    usage = response.usage
    input_tokens = (
        usage.input_tokens
        + (usage.cache_creation_input_tokens or 0)
        + (usage.cache_read_input_tokens or 0)
    )
    log.info("sketch: %s used %d input and %d output tokens",
             response.model, input_tokens, usage.output_tokens)  # fmt: skip
    try:
        data = json.loads(answer)
    except ValueError:
        raise VisionError("sketch_failed") from None
    return Look(data, str(response.model), input_tokens, usage.output_tokens)


def content(ask: SketchAsk) -> list[dict[str, Any]]:
    """The user message: the photo first (cached), then the draft for a check round."""
    blocks: list[dict[str, Any]] = [
        {"type": "text", "text": f"Image 1, the sketch ({ask.width} x {ask.height} pixels):"},
        {**_image(ask.photo_png), "cache_control": {"type": "ephemeral"}},
    ]
    if ask.ink is not None:
        x0, y0, x1, y1 = ask.ink
        blocks.append(
            {
                "type": "text",
                "text": f"A program measured the dark pixels of image 1: they span x {x0} to "
                f"{x1} and y {y0} to {y1}. That is the drawing's outer edge unless something "
                "else dark is in the photo (a shadow, the paper's edge, writing beside the "
                "plan). Use it to place and size the plan.",
            }
        )
    if ask.draft_png is None or ask.draft is None:
        blocks.append({"type": "text", "text": "Return the plan of this sketch."})
        return blocks
    plan = json.dumps(ask.draft, separators=(",", ":"))
    blocks += [
        {"type": "text", "text": "Image 2, your draft in red over the sketch (same size):"},
        _image(ask.draft_png),
        {"type": "text", "text": CHECK_TEXT + plan},
    ]
    return blocks


def _image(png: bytes) -> dict[str, Any]:
    data = base64.standard_b64encode(png).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}


@lru_cache
def _client(timeout: float) -> anthropic.Anthropic:
    # Credentials come from the environment (ANTHROPIC_API_KEY), never from code. No row
    # lock is held during the call (see sketch_service.py), so the SDK may retry.
    return anthropic.Anthropic(timeout=timeout, max_retries=2)
