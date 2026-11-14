"""The sketch redraw's plan: which pages get it, reading the model's answer, the cache.

Expected values are worked out by hand in the comment next to each assertion.
"""

import pytest

from app.domain.sketch import (
    SKETCH_MODE,
    Door,
    Note,
    Plan,
    Room,
    Wall,
    Window,
    claim_is_live,
    is_sketch_page,
    parse_plan,
    plan_json,
    says_matches,
    scale_plan,
    sketch_cache_entry,
)
from app.domain.upscale import UPSCALE_FORMAT, is_cached

W, H = 1000, 800  # the image as sent


def _wall(x0: float, y0: float, x1: float, y1: float, outer: bool = True) -> dict[str, object]:
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "outer": outer}


def _answer(**lists: object) -> dict[str, object]:
    base: dict[str, object] = {
        "matches": False, "walls": [], "doors": [], "windows": [], "rooms": [], "texts": [],
    }  # fmt: skip
    return {**base, **lists}


# --- which pages ----------------------------------------------------------------


def test_only_raster_image_documents_are_sketch_pages() -> None:
    assert is_sketch_page("image") is True
    for kind in ("pdf", "svg", "dxf", "dwg", "ifc"):
        assert is_sketch_page(kind) is False


# --- reading the answer ---------------------------------------------------------


def test_reads_every_part_of_a_plan() -> None:
    door = {"x0": 100, "y0": 20, "x1": 160, "y1": 20, "hinge": "end",
            "opens_toward_x": 130, "opens_toward_y": 60}  # fmt: skip
    outline = [{"x": 10, "y": 20}, {"x": 510, "y": 20}, {"x": 510, "y": 420}]
    raw = _answer(
        walls=[_wall(10, 20, 510, 20), _wall(10, 20, 10, 420, outer=False)],
        doors=[door],
        windows=[{"x0": 300, "y0": 20, "x1": 380, "y1": 20}],
        rooms=[{"name": " bedroom ", "x": 120, "y": 100, "outline": outline}],
        texts=[{"text": "N", "x": 900, "y": 50}],
    )
    plan = parse_plan(raw, W, H)

    assert plan.walls == (
        Wall((10, 20), (510, 20), outer=True),
        Wall((10, 20), (10, 420), outer=False),
    )
    # "hinge": "end" means the hinge is at (x1, y1).
    assert plan.doors == (Door((100, 20), (160, 20), hinge_at_a=False, toward=(130, 60)),)
    assert plan.windows == (Window((300, 20), (380, 20)),)
    # The name is trimmed but otherwise kept exactly as written.
    assert plan.rooms == (Room("bedroom", (120, 100), ((10, 20), (510, 20), (510, 420))),)
    assert plan.notes == (Note("N", (900, 50)),)


def test_an_answer_without_plan_lists_is_refused() -> None:
    with pytest.raises(ValueError):
        parse_plan({"elements": []}, W, H)
    with pytest.raises(ValueError):
        parse_plan(["walls"], W, H)


@pytest.mark.parametrize(
    "wall",
    [
        _wall(10, 20, 10, 20),  # zero length
        _wall(10, 20, 10.5, 20.5),  # about 0.7 px: shorter than MIN_LENGTH_PX (1)
        _wall(-5, 20, 100, 20),  # starts off the page
        _wall(10, 20, 100, 801),  # ends below the page (H = 800)
        {"x0": 10, "y0": 20, "x1": "100", "y1": 20, "outer": True},  # a string, not a number
        {"x0": 10, "y0": 20, "x1": float("nan"), "y1": 20, "outer": True},
        {"x0": 10, "y0": 20, "x1": True, "y1": 20, "outer": True},  # a bool is not a number
        {"x0": 10, "y0": 20, "x1": 100, "y1": 20},  # no thickness class
        "a wall",
    ],
)
def test_a_malformed_or_off_page_wall_is_skipped_not_repaired(wall: object) -> None:
    plan = parse_plan(_answer(walls=[wall, _wall(0, 0, 1000, 0)]), W, H)
    assert plan.walls == (Wall((0, 0), (1000, 0), outer=True),)  # the page edge itself is on it


def test_a_door_needs_a_hinge_end_and_a_side_to_open_to() -> None:
    door = {"x0": 100, "y0": 20, "x1": 160, "y1": 20, "hinge": "start",
            "opens_toward_x": 130, "opens_toward_y": 60}  # fmt: skip
    plan = parse_plan(
        _answer(
            doors=[
                door,
                {**door, "hinge": "middle"},
                # A point on the door's own line says nothing about the side.
                {**door, "opens_toward_x": 400, "opens_toward_y": 20},
                {**door, "opens_toward_y": 900},  # off the page
            ]
        ),
        W,
        H,
    )
    assert plan.doors == (Door((100, 20), (160, 20), hinge_at_a=True, toward=(130, 60)),)


def test_rooms_need_a_written_name_and_keep_a_bad_outline_out() -> None:
    plan = parse_plan(
        _answer(
            rooms=[
                {"name": "", "x": 1, "y": 1, "outline": []},
                {"name": "kitchen", "x": 2000, "y": 1, "outline": []},  # label off the page
                {"name": "hall", "x": 5, "y": 5, "outline": [{"x": 1, "y": 1}, {"x": 2, "y": 2}]},
                {"name": "wc", "x": 5, "y": 5,
                 "outline": [{"x": 1, "y": 1}, {"x": 9, "y": 1}, {"x": 9, "y": -1}]},
            ]
        ),
        W,
        H,
    )  # fmt: skip
    # Two points are no outline; an off-page corner spoils the outline, not the room.
    assert plan.rooms == (Room("hall", (5, 5), None), Room("wc", (5, 5), None))


def test_blank_texts_are_skipped() -> None:
    plan = parse_plan(_answer(texts=[{"text": "  ", "x": 1, "y": 1}, {"text": "x", "x": 1}]), W, H)
    assert plan.notes == ()


def test_matches_only_counts_when_the_model_says_so_plainly() -> None:
    assert says_matches({"matches": True}) is True
    assert says_matches({"matches": "true"}) is False
    assert says_matches({}) is False
    assert says_matches(None) is False


# --- moving between image and page pixels ---------------------------------------


def test_scaling_a_plan_moves_every_point_and_nothing_else() -> None:
    plan = Plan(
        walls=(Wall((10, 20), (30, 20), outer=False),),
        doors=(Door((10, 20), (20, 20), hinge_at_a=True, toward=(15, 30)),),
        windows=(Window((22, 20), (28, 20)),),
        rooms=(Room("bath", (15, 40), ((10, 20), (30, 20), (30, 60))),),
        notes=(Note("2.4 m", (5, 5)),),
    )
    doubled = scale_plan(plan, 2.0)
    assert doubled == Plan(
        walls=(Wall((20, 40), (60, 40), outer=False),),
        doors=(Door((20, 40), (40, 40), hinge_at_a=True, toward=(30, 60)),),
        windows=(Window((44, 40), (56, 40)),),
        rooms=(Room("bath", (30, 80), ((20, 40), (60, 40), (60, 120))),),
        notes=(Note("2.4 m", (10, 10)),),
    )


def test_plan_json_is_the_answer_schema_again() -> None:
    plan = Plan(
        walls=(Wall((10.04, 20), (30, 20), outer=True),),
        doors=(Door((10, 20), (20, 20), hinge_at_a=False, toward=(15, 30)),),
        windows=(),
        rooms=(Room("bath", (15, 40), None),),
        notes=(),
    )
    data = plan_json(plan)
    # Rounded to 0.1 px: 10.04 -> 10.0.
    assert data["walls"] == [{"x0": 10.0, "y0": 20, "x1": 30, "y1": 20, "outer": True}]
    assert data["rooms"] == [{"name": "bath", "x": 15, "y": 40, "outline": []}]
    # Reading it back gives the same plan (rounding aside).
    again = parse_plan({**data, "matches": False}, 100, 100)
    assert again.doors == plan.doors and again.rooms == plan.rooms


# --- cache and the running claim ------------------------------------------------


def test_a_sketch_entry_is_cached_for_its_version_and_only_as_a_sketch() -> None:
    entry = sketch_cache_entry(4, "claude-opus-5-5", 23, rounds=2, matched=True,
                               input_tokens=9000, output_tokens=3000)  # fmt: skip
    assert entry == {
        "document_version": 4, "format": UPSCALE_FORMAT, "mode": SKETCH_MODE,
        "model": "claude-opus-5-5", "added": 23, "rounds": 2, "matched": True,
        "input_tokens": 9000, "output_tokens": 3000,
    }  # fmt: skip
    meta = {"upscale": entry}
    assert is_cached(meta, 4, mode=SKETCH_MODE) is True
    assert is_cached(meta, 5, mode=SKETCH_MODE) is False
    # A gap-filling entry on an image page does not count as its sketch redraw.
    assert is_cached(meta, 4, mode="fill") is False


def test_a_claim_is_live_until_it_is_stale() -> None:
    claim = {"token": "t", "started_s": 1000.0}
    assert claim_is_live(claim, now_s=1000.0, stale_after_s=600) is True
    assert claim_is_live(claim, now_s=1599.0, stale_after_s=600) is True  # 599 s in
    assert claim_is_live(claim, now_s=1600.0, stale_after_s=600) is False  # 600 s: stale
    assert claim_is_live(None, now_s=1000.0, stale_after_s=600) is False
    assert claim_is_live({"token": "t"}, now_s=1000.0, stale_after_s=600) is False
