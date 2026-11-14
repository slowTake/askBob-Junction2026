"""The sketch redraw's loop (#82): draw, compare, correct.

Round 1: the model authors the whole plan from the photo. Each later round: the tidied
draft is drawn in red over the photo with the same shapes the frontend draws, and the
model compares the two and either says it matches or returns a corrected plan. The loop
stops when it matches, after `max_rounds`, or when `time_left()` says no new round may
start.

The model call and the render are passed in, so tests never reach the network.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.domain.sketch import Plan, parse_plan, plan_json, says_matches, scale_plan
from app.domain.sketch_drawing import Shape, sketch_shapes
from app.domain.sketch_text import Word, confirm_written
from app.domain.sketch_tidy import tidy
from app.upscale.sketch_model import SketchAsk
from app.upscale.vision import Look, VisionError

log = logging.getLogger(__name__)

Asker = Callable[[SketchAsk], Look]
Renderer = Callable[[list[Shape]], bytes]  # page-pixel shapes -> PNG at the sent size


@dataclass(frozen=True)
class Redraw:
    plan: Plan  # page pixels, tidied
    shapes: list[Shape]
    rounds: int  # model calls made
    matched: bool  # the model said the last draft matches the sketch
    model: str
    input_tokens: int
    output_tokens: int


def run_loop(
    photo_png: bytes,
    width: int,
    height: int,
    page_w: float,
    page_h: float,
    *,
    max_rounds: int,
    ask: Asker,
    render: Renderer,
    words: Sequence[Word],
    time_left: Callable[[], bool],
    ink: tuple[int, int, int, int] | None = None,
) -> Redraw:
    """Raises VisionError when the first round fails; a later failure keeps the draft."""
    scale = width / page_w

    def page_plan(look: Look) -> Plan:
        plan = scale_plan(parse_plan(look.data, width, height), 1 / scale)
        return confirm_written(tidy(plan, page_w, page_h), words, page_w, page_h)

    look = ask(SketchAsk(photo_png, width, height, ink=ink))
    tokens = [look.input_tokens, look.output_tokens]
    model = look.model
    try:
        plan = page_plan(look)
    except ValueError:
        raise VisionError("sketch_failed") from None
    if not plan.walls:
        raise VisionError("sketch_unreadable")

    rounds, matched = 1, False
    while rounds < max_rounds and time_left():
        shapes = sketch_shapes(plan, page_w, page_h)
        draft = SketchAsk(
            photo_png, width, height, render(shapes), plan_json(scale_plan(plan, scale)), ink
        )
        rounds += 1
        try:
            look = ask(draft)
        except VisionError as exc:
            log.warning("sketch: check round %d failed (%s); keeping the draft", rounds, exc.code)
            break
        tokens = [tokens[0] + look.input_tokens, tokens[1] + look.output_tokens]
        model = look.model
        if says_matches(look.data):
            matched = True
            break
        try:
            corrected = page_plan(look)
        except ValueError:
            log.warning("sketch: check round %d answered no plan; keeping the draft", rounds)
            break
        if not corrected.walls:
            log.warning("sketch: check round %d dropped every wall; keeping the draft", rounds)
            break
        plan = corrected

    return Redraw(
        plan, sketch_shapes(plan, page_w, page_h), rounds, matched, model, tokens[0], tokens[1]
    )
