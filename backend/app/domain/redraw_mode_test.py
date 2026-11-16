from app.domain.redraw_mode import (
    PLAN_MODE,
    SKETCH_MODE,
    PageStats,
    page_redraw_mode,
    redraw_mode,
    stats_from_meta,
    stats_meta,
)
from app.domain.upscale import UPSCALE_FORMAT

# A scanned printed plan with nothing but ruled line work: half its ink in long straight
# runs, flat paper, no fills, no dimensions read.
RULED_SCAN = PageStats(straight_share=0.5, fill_share=0.0, dimension_words=0, paper_spread=5.0)
# A phone photo of a hand drawing: wobbly lines, a shadow across the paper.
NAPKIN = PageStats(straight_share=0.1, fill_share=0.0, dimension_words=0, paper_spread=40.0)


def test_only_raster_image_pages_can_be_sketches() -> None:
    # PDF, SVG, DXF, DWG and IFC pages keep the page redraw whatever they look like (D-027).
    for kind in ("pdf", "svg", "dxf", "dwg", "ifc"):
        assert redraw_mode(kind, NAPKIN) == PLAN_MODE
        assert redraw_mode(kind, None) == PLAN_MODE


def test_an_image_page_without_statistics_keeps_the_old_rule() -> None:
    # Ingested before #138: every raster image page was a sketch (D-028).
    assert redraw_mode("image", None) == SKETCH_MODE


def test_a_photo_of_a_hand_drawing_is_a_sketch() -> None:
    assert redraw_mode("image", NAPKIN) == SKETCH_MODE


def test_ruled_line_work_on_flat_paper_is_a_plan() -> None:
    assert redraw_mode("image", RULED_SCAN) == PLAN_MODE


def test_ruled_line_work_on_shadowed_paper_is_not_enough() -> None:
    # 0.5 straight would be a plan on a scan, but a photo's shadow (spread 40 >= 30) asks
    # for more: a carefully drawn sketch has straight lines too.
    shadowed = PageStats(straight_share=0.5, fill_share=0.0, dimension_words=0, paper_spread=40.0)
    assert redraw_mode("image", shadowed) == SKETCH_MODE


def test_thresholds_are_inclusive_where_they_say_plan() -> None:
    # Straight share at exactly 0.35 on paper just under the 30-level cut: a plan.
    edge = PageStats(straight_share=0.35, fill_share=0.0, dimension_words=0, paper_spread=29.9)
    assert redraw_mode("image", edge) == PLAN_MODE
    # Just under 0.35 straight: a sketch.
    below = PageStats(straight_share=0.349, fill_share=0.0, dimension_words=0, paper_spread=0.0)
    assert redraw_mode("image", below) == SKETCH_MODE
    # Paper spread at exactly 30 levels counts as a photo.
    photo = PageStats(straight_share=0.9, fill_share=0.0, dimension_words=0, paper_spread=30.0)
    assert redraw_mode("image", photo) == SKETCH_MODE


def test_colour_fills_make_a_plan_even_on_a_photo() -> None:
    # 5 % of the page in light colour fills: room colours of a printed plan.
    filled = PageStats(straight_share=0.1, fill_share=0.05, dimension_words=0, paper_spread=40.0)
    assert redraw_mode("image", filled) == PLAN_MODE
    sparse = PageStats(straight_share=0.1, fill_share=0.049, dimension_words=0, paper_spread=40.0)
    assert redraw_mode("image", sparse) == SKETCH_MODE


def test_three_dimensions_read_make_a_plan() -> None:
    # Three OCR words read as dimensions: printed dimension strings. A sketch's
    # handwriting rarely reads as one, and once is not enough.
    three = PageStats(straight_share=0.1, fill_share=0.0, dimension_words=3, paper_spread=40.0)
    assert redraw_mode("image", three) == PLAN_MODE
    two = PageStats(straight_share=0.1, fill_share=0.0, dimension_words=2, paper_spread=40.0)
    assert redraw_mode("image", two) == SKETCH_MODE


def test_statistics_round_trip_through_page_meta() -> None:
    meta = stats_meta(RULED_SCAN)
    assert meta == {
        "straight_share": 0.5, "fill_share": 0.0, "dimension_words": 0, "paper_spread": 5.0,
    }  # fmt: skip
    assert stats_from_meta(meta) == RULED_SCAN


def test_statistics_are_rounded_for_storage() -> None:
    stats = PageStats(straight_share=0.47123, fill_share=0.57449, dimension_words=9,
                      paper_spread=20.04)  # fmt: skip
    # Shares to 3 decimals, the spread to 1: finer than any threshold, short in JSON.
    assert stats_meta(stats) == {
        "straight_share": 0.471, "fill_share": 0.574, "dimension_words": 9, "paper_spread": 20.0,
    }  # fmt: skip


def test_malformed_statistics_are_none_not_repaired() -> None:
    good = stats_meta(NAPKIN)
    assert stats_from_meta(None) is None
    assert stats_from_meta("stats") is None
    assert stats_from_meta({k: v for k, v in good.items() if k != "fill_share"}) is None
    assert stats_from_meta({**good, "straight_share": "0.5"}) is None
    assert stats_from_meta({**good, "dimension_words": True}) is None
    assert stats_from_meta({**good, "dimension_words": 2.5}) is None
    assert stats_from_meta({**good, "paper_spread": float("nan")}) is None
    assert stats_from_meta({**good, "fill_share": -0.1}) is None


def _upscaled(mode: str, fmt: int = UPSCALE_FORMAT) -> dict[str, object]:
    return {"upscale": {"format": fmt, "mode": mode, "added": 1, "document_version": 1}}


def test_a_page_redraws_as_its_statistics_say() -> None:
    assert page_redraw_mode("image", {"page_stats": stats_meta(RULED_SCAN)}) == PLAN_MODE
    assert page_redraw_mode("image", {"page_stats": stats_meta(NAPKIN)}) == SKETCH_MODE
    assert page_redraw_mode("image", {}) == SKETCH_MODE  # ingested before #138
    assert page_redraw_mode("image", {"page_stats": {"broken": 1}}) == SKETCH_MODE
    assert page_redraw_mode("pdf", {}) == PLAN_MODE


def test_a_redraw_that_ran_says_which_mode_the_page_has() -> None:
    # A page redrawn with ?mode= the other way shows what was drawn, not the guess.
    napkin = {"page_stats": stats_meta(NAPKIN)}
    assert page_redraw_mode("image", {**napkin, **_upscaled("fill")}) == PLAN_MODE
    ruled = {"page_stats": stats_meta(RULED_SCAN)}
    assert page_redraw_mode("image", {**ruled, **_upscaled("sketch")}) == SKETCH_MODE
    # A redraw under older rules runs again, so it says nothing.
    assert page_redraw_mode("image", {**ruled, **_upscaled("sketch", UPSCALE_FORMAT - 1)}) == (
        PLAN_MODE
    )


def test_a_page_with_matched_cad_rooms_is_a_plan() -> None:
    # Its clean sheet is the CAD geometry, and upscaling it does nothing (D-030).
    assert page_redraw_mode("image", {"companion_dxf": {"rooms": 3}}) == PLAN_MODE
