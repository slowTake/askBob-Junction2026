"""The draw, compare, correct loop, with a scripted fake model and a fake render.

The page is 2000 x 2000 px, sent at 1000 x 1000 (scale 0.5): the model answers in
image pixels, the plan comes back in page pixels (doubled).
"""

from typing import Any

import pytest

from app.domain.sketch import Plan, Room, Wall
from app.domain.sketch_drawing import Shape
from app.domain.sketch_text import Word
from app.upscale.sketch_loop import Redraw, run_loop
from app.upscale.sketch_model import SketchAsk
from app.upscale.vision import Look, VisionError

PHOTO = b"photo"


def _plan(*walls: tuple[float, float, float, float], **extra: Any) -> dict[str, Any]:
    return {
        "matches": False,
        "walls": [{"x0": a, "y0": b, "x1": c, "y1": d, "outer": True} for a, b, c, d in walls],
        "doors": [], "windows": [], "rooms": [], "texts": [],
        **extra,
    }  # fmt: skip


FIRST = _plan((100, 100, 900, 100))
SECOND = _plan((100, 100, 900, 100), (900, 100, 900, 900))


class Script:
    """Answers in order; records what each round was sent."""

    def __init__(self, *answers: object) -> None:
        self.answers = list(answers)
        self.asks: list[SketchAsk] = []
        self.renders: list[list[Shape]] = []

    def ask(self, ask: SketchAsk) -> Look:
        self.asks.append(ask)
        answer = self.answers.pop(0)
        if isinstance(answer, VisionError):
            raise answer
        return Look(answer, "fake-opus", 1000, 200)

    def render(self, shapes: list[Shape]) -> bytes:
        self.renders.append(list(shapes))
        return f"render {len(self.renders)}".encode()

    def run(
        self, max_rounds: int = 3, time_left: bool = True, words: list[Word] | None = None
    ) -> Redraw:
        return run_loop(
            PHOTO, 1000, 1000, 2000, 2000,
            max_rounds=max_rounds, ask=self.ask, render=self.render,
            words=words or [], time_left=lambda: time_left,
        )  # fmt: skip


def test_stops_when_the_model_says_its_draft_matches() -> None:
    script = Script(FIRST, {**FIRST, "matches": True})
    result = script.run()

    assert result.rounds == 2 and result.matched is True
    # (100, 100)-(900, 100) in image pixels is (200, 200)-(1800, 200) on the page.
    assert result.plan.walls == (Wall((200, 200), (1800, 200), outer=True),)
    first, check = script.asks
    assert (first.draft_png, first.draft) == (None, None)
    # The check round sees the render of the tidied draft, and its plan in image pixels.
    assert check.photo_png == PHOTO and check.draft_png == b"render 1"
    assert check.draft is not None and check.draft["walls"] == FIRST["walls"]
    assert [s.kind for s in script.renders[0]] == ["wall"]
    # Tokens add up over both rounds; the model is the one that answered.
    assert (result.model, result.input_tokens, result.output_tokens) == ("fake-opus", 2000, 400)


def test_a_correction_replaces_the_draft_and_is_checked_again() -> None:
    script = Script(FIRST, SECOND, {**SECOND, "matches": True})
    result = script.run()
    assert result.rounds == 3 and result.matched is True
    assert len(result.plan.walls) == 2
    assert script.asks[2].draft_png == b"render 2"


def test_stops_after_the_last_round_with_the_last_correction() -> None:
    script = Script(FIRST, SECOND)
    result = script.run(max_rounds=2)
    assert result.rounds == 2 and result.matched is False
    assert len(result.plan.walls) == 2  # the correction is kept, though not checked again


def test_one_round_is_just_the_first_draft() -> None:
    result = Script(FIRST).run(max_rounds=1)
    assert result.rounds == 1 and result.matched is False and len(result.plan.walls) == 1


def test_no_check_round_starts_after_the_deadline() -> None:
    script = Script(FIRST, SECOND)
    result = script.run(time_left=False)
    assert result.rounds == 1 and len(script.asks) == 1


def test_a_first_answer_without_walls_is_unreadable() -> None:
    with pytest.raises(VisionError) as caught:
        Script(_plan()).run()
    assert caught.value.code == "sketch_unreadable"
    with pytest.raises(VisionError) as caught:
        Script({"elements": []}).run()
    assert caught.value.code == "sketch_failed"


def test_a_first_round_failure_is_the_loop_failure() -> None:
    with pytest.raises(VisionError) as caught:
        Script(VisionError("llm_busy")).run()
    assert caught.value.code == "llm_busy"


def test_a_failed_check_round_keeps_the_draft_it_had() -> None:
    for broken in (VisionError("llm_unavailable"), {"walls": "?"}, _plan()):
        result = Script(FIRST, broken).run()
        assert result.rounds == 2 and result.matched is False
        assert result.plan.walls == (Wall((200, 200), (1800, 200), outer=True),)


def test_numbers_nobody_wrote_never_reach_the_draft() -> None:
    answer = _plan(
        (100, 100, 900, 100),
        rooms=[{"name": "bedroom 3x4m", "x": 500, "y": 500, "outline": []}],
        texts=[{"text": "12 m²", "x": 500, "y": 600}],
    )
    result = Script(answer).run(max_rounds=1)
    # No OCR word confirms either number: the text goes, the room keeps its name.
    assert result.plan.rooms == (Room("bedroom", (1000, 1000), None),)
    assert result.plan.notes == ()


def test_the_result_is_drawn_in_page_pixels() -> None:
    result = Script(FIRST).run(max_rounds=1)
    [wall] = result.shapes
    assert wall.properties["segment_px"] == [[200, 200], [1800, 200]]
    assert isinstance(result.plan, Plan)


def test_the_ink_box_goes_to_every_round() -> None:
    script = Script(FIRST, {"matches": True})
    run_loop(
        PHOTO, 1000, 1000, 2000, 2000,
        max_rounds=3, ask=script.ask, render=script.render, words=[],
        time_left=lambda: True, ink=(100, 90, 910, 905),
    )  # fmt: skip
    assert [a.ink for a in script.asks] == [(100, 90, 910, 905), (100, 90, 910, 905)]
