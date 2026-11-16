import json

import numpy as np
import pytest

from app.domain.tokens import Word
from eval.redraw_bench import (
    IMAGE,
    OCR,
    VISION,
    confidence,
    confidence_table,
    page,
    read_words,
    recorded_vision,
    recorded_words,
    redraw,
    report,
    table,
    truth_shapes,
)
from eval.redraw_bench import TRUTH as TRUTH_FILE
from eval.redraw_render import opening_mask, wall_mask
from eval.redraw_sheet import Opening, Room, Sheet, Text, Wall, load_sheet

W, H = 482, 507  # the benchmark page: tolerances are 2 px (walls, ink) and 4 px (positions)

TRUTH = Sheet(
    walls=(Wall(((20, 90), (180, 90), (180, 110), (20, 110))),),
    openings=(Opening("door", (50, 50), (90, 50)),),
    rooms=(Room("mh", (100, 150)),),
    texts=(Text("5,341", "dimension", (100, 30)),),
)


def test_a_redraw_equal_to_the_truth_scores_everything() -> None:
    # The ink is what the redraw draws: the wall and the door's line (it has no swing).
    ink = wall_mask(TRUTH.walls, W, H) | opening_mask(TRUTH.openings, W, H)
    r = report(TRUTH, TRUTH, ink, W, H)
    assert r.wall_tolerance_px == pytest.approx(2.0)  # 2/482 of a 482 px page
    assert r.position_tolerance_px == pytest.approx(4.0)
    assert (r.walls.recall, r.walls.precision) == (1.0, 1.0)
    assert r.openings.found.matched == 1
    assert r.openings.swings_checked == 0  # the truth door gives no hinge
    assert r.rooms.named.matched == 1 and r.rooms.outlined == 0  # no outlines to compare
    t = r.texts
    assert (t.found.matched, t.exact, t.digits, t.kind_ok, t.rotation_ok) == (1, 1, 1, 1, 1)
    # The ink is the truth walls and the door line 40 px away: all walls found, the
    # door's 41 px (x 50..90) are off them.
    assert r.ink_finds_walls == 1.0
    assert r.ink_off_walls == pytest.approx(41 / (3381 + 41))
    # The redraw is that same ink: all of the ink redrawn, all of the redraw on ink.
    assert (r.ink_redrawn, r.redraw_on_ink) == (1.0, 1.0)


def test_an_empty_redraw_on_blank_paper() -> None:
    r = report(Sheet(), TRUTH, np.zeros((H, W), dtype=bool), W, H)
    # Nothing drawn: no truth covered, and nothing drawn wrong.
    assert (r.walls.recall, r.walls.precision) == (0.0, 1.0)
    assert (r.openings.found.matched, r.rooms.named.matched, r.texts.found.matched) == (0, 0, 0)
    assert (r.ink_finds_walls, r.ink_off_walls) == (0.0, 0.0)  # no ink: none of it is false
    # No ink to redraw and no redraw to place: neither has anything wrong.
    assert (r.ink_redrawn, r.redraw_on_ink) == (1.0, 1.0)


def test_ink_away_from_the_walls_is_off_walls_and_not_redrawn() -> None:
    walls = Sheet(walls=TRUTH.walls)
    ink = wall_mask(TRUTH.walls, W, H)
    ink[300:310, 300:310] = True  # 100 px, far from the wall
    r = report(walls, walls, ink, W, H)
    assert r.ink_finds_walls == 1.0
    # The filled band is 161 x 21 px (x 20..180, y 90..110, edges included) = 3381 px.
    assert r.ink_off_walls == pytest.approx(100 / (3381 + 100))
    # The redraw (the band) leaves the 100 px blob out, and all of it lies on ink.
    assert r.ink_redrawn == pytest.approx(3381 / (3381 + 100))
    assert r.redraw_on_ink == 1.0


def test_redraw_on_blank_paper_is_not_on_ink() -> None:
    # Ink is the band only; the redraw draws the band and a 10 x 10 box 100 px away from it.
    ink = wall_mask(TRUTH.walls, W, H)
    extra = Wall(((300, 300), (309, 300), (309, 309), (300, 309)))
    r = report(Sheet(walls=(*TRUTH.walls, extra)), TRUTH, ink, W, H)
    assert r.ink_redrawn == 1.0
    # The box fills x 300..309, y 300..309 with edges: 100 px off the ink of 3381 + 100.
    assert r.redraw_on_ink == pytest.approx(3381 / (3381 + 100))


def test_a_redraw_on_a_coloured_symbol_is_on_the_page() -> None:
    # The page's lines are the band and a 10 x 10 door arc drawn in colour: not ink.
    ink = wall_mask(TRUTH.walls, W, H)
    lines = ink.copy()
    lines[300:310, 300:310] = True
    extra = Wall(((300, 300), (309, 300), (309, 309), (300, 309)))
    r = report(Sheet(walls=(*TRUTH.walls, extra)), TRUTH, ink, W, H, lines)
    assert r.redraw_on_ink == 1.0  # all of it on the page's lines
    assert r.ink_redrawn == 1.0  # and the ink is all redrawn


def test_positions_count_within_four_pixels() -> None:
    near = Sheet(texts=(Text("5,341", "dimension", (103, 30)),))  # 3 px off
    far = Sheet(texts=(Text("5,341", "dimension", (105, 30)),))  # 5 px off
    ink = np.zeros((H, W), dtype=bool)
    assert report(near, TRUTH, ink, W, H).texts.found.matched == 1
    assert report(far, TRUTH, ink, W, H).texts.found.matched == 0


def test_the_table_shows_the_numbers() -> None:
    walls = Sheet(walls=TRUTH.walls)
    text = table(report(walls, walls, wall_mask(TRUTH.walls, W, H), W, H))
    assert "recall 100.0%" in text and "off walls   0.0%" in text and "on ink 100.0%" in text


def test_the_truth_is_drawn_as_the_view_draws_for_its_ceiling_score() -> None:
    shapes = truth_shapes(TRUTH, W)
    assert [s.part for s in shapes] == ["walls", "rooms", "dimensions"]  # no opening
    assert shapes[0].polygon == TRUTH.walls[0].polygon
    # "mh" at (100, 150) in the room size 1.5 x 4.82 = 7.23 px: half width
    # 0.6 x 7.23 x 2 / 2 = 4.338, half height 3.615 (as drawn_shape does it).
    (x0, y0), _, (x1, y1), _ = shapes[1].polygon
    assert (x0, y0, x1, y1) == pytest.approx((95.662, 146.385, 104.338, 153.615))


def test_the_confidence_line_shows_the_score_and_its_parts() -> None:
    layers, _ = page(IMAGE)
    c = confidence(layers, [])  # nothing drawn on a page with ink: all of it missed
    assert (c.covered, c.on_ink, c.score) == (0.0, 1.0, 0.0)
    text = confidence_table("confidence", c)
    assert "score 0.0%" in text and "covered 0.0%" in text and "walls 0 (100.0% on ink" in text


def test_recorded_words_are_read_whole_or_refused() -> None:
    raw = {"words": [{"bbox": [0, 0, 10, 4], "text": "mh", "confidence": 0.5}]}
    assert recorded_words(raw) == [Word((0, 0, 10, 4), "mh", 0.5)]
    with pytest.raises(ValueError):
        recorded_words({"words": [{"bbox": [0, 0], "text": "mh", "confidence": 0.5}]})


def test_recorded_vision_is_used_only_when_the_service_answered() -> None:
    assert recorded_vision({"status": "unavailable"}) is None
    assert recorded_vision({"status": "skipped"}) is None
    used = recorded_vision({"status": "used", "data": {"walls": [[[0, 0], [9, 0], [9, 2]]]}})
    assert used is not None and len(used.walls) == 1
    with pytest.raises(ValueError):
        recorded_vision({})


def test_redraw_runs_ingest_on_the_recorded_reading() -> None:
    blank = np.full((60, 120), 255, dtype=np.uint8)  # no ink: no walls are found
    words = [Word((10, 20, 40, 28), "5341", 0.9), Word((60, 20, 90, 28), "5,341", 0.5)]
    sheet = redraw(blank, words, None)
    # Both are dimensions, drawn at their box centres ((10+40)/2, (20+28)/2) and
    # ((60+90)/2, 24). "5,341" is metres with a decimal comma (#36); classified text is
    # drawn whatever its confidence, so 0.5 doesn't hide it.
    assert sheet == Sheet(
        texts=(Text("5341", "dimension", (25, 24)), Text("5,341", "dimension", (75, 24)))
    )


def test_the_recorded_reading_loses_only_line_work() -> None:
    # The recording is RapidOCR's raw reading; ingest drops line work from it (D-052).
    # Of colorful-34's 39 recorded words only "1281" goes: looked at by eye, its box is
    # the stove in the kitchen (a frame open at the top round four burners). The red
    # heights, decimal-comma dimensions and handwritten names ("mh", "Keittiö") stay.
    layers, _ = page(IMAGE)
    raw = json.loads(OCR.read_text(encoding="utf-8"))
    kept = read_words(layers, raw)
    dropped = [w.text for w in recorded_words(raw) if w not in kept]
    assert (len(raw["words"]), dropped) == (39, ["1281"])


# The benchmark itself, offline: recorded OCR and vision answers, the hand-made truth.
# These floors are the baseline recorded on 2026-11-16 (D-049), raised by the vocabulary
# work (D-050), colour separation (D-051), dropping line work from OCR (D-052) and
# traced walls (D-053) and doors and windows (D-055); they are recorded values, not worked
# out by hand, and stop a
# change from making the redraw of colorful-34 worse. A PR that improves a number raises
# its floor; one that has to lower a floor says why in its decision.
FLOORS = {
    # Ratios are rounded down: 0.96488 recorded, 0.96464 with doors and windows (D-055).
    "walls recall": 0.964,
    # D-053 lowered this from 0.969: 3 thick walls became the whole wall network, with
    # fixtures and handwriting that touch the walls (0.80495 recorded). D-055: window
    # frames and door leaves and arcs are no longer traced as wall (0.83554 recorded).
    # D-057 lowers it: the false doors on stools, a table and a threshold carved those
    # fixtures' rings out of the walls; without them the rings are wall again (fixtures
    # are a separate issue). 0.82632 recorded with doors' gaps on a wall, 0.82144 with
    # wall corners no longer read as leaves, 0.81959 with circles no longer read as arcs.
    "walls precision": 0.819,
    "openings found": 24,  # D-057: 12 windows and 12 doors of 34
    "openings swings": 11,  # D-057: 11 of the 12 doors the truth gives a swing for
    "rooms named": 3,
    "rooms outlined": 3,
    "texts found": 25,
    "texts precision": 0.862,  # D-052: the stove is no longer drawn as "1281"; 25/29
    "texts exact": 11,
    "texts digits": 13,
    "texts kind": 16,  # #36: decimal-comma dimensions and h-heights have their kind
    # D-055: read against the symbol layer, as the redraw now draws coloured door arcs
    # and window frames that are not ink (0.99940 recorded; 0.99822 on the ink, walls only).
    # D-057 lowers it: a door is stored on its wall's centre line, as CAD draws it, and its
    # arc is drawn round that hinge, 3-4 px off the arc the scan draws from a band's edge
    # (0.99724 recorded).
    "redraw on ink": 0.997,
    "ink redrawn": 0.808,  # 0.80847 recorded: doors and windows are drawn (D-055)
}


def test_the_benchmark_does_not_get_worse() -> None:
    layers, _ = page(IMAGE)
    height, width = layers.ink_page.shape
    ocr, vision = (json.loads(p.read_text(encoding="utf-8")) for p in (OCR, VISION))
    truth = load_sheet(json.loads(TRUTH_FILE.read_text(encoding="utf-8")), width, height)
    sheet = redraw(layers.ink_page, read_words(layers, ocr), recorded_vision(vision), layers)
    r = report(sheet, truth, layers.ink, width, height, layers.symbols)
    now = {
        "walls recall": r.walls.recall,
        "walls precision": r.walls.precision,
        "openings found": r.openings.found.matched,
        "openings swings": r.openings.swings_ok,
        "rooms named": r.rooms.named.matched,
        "rooms outlined": r.rooms.outlined,
        "texts found": r.texts.found.matched,
        "texts precision": r.texts.found.precision,
        "texts exact": r.texts.exact,
        "texts digits": r.texts.digits,
        "texts kind": r.texts.kind_ok,
        "redraw on ink": r.redraw_on_ink,
        "ink redrawn": r.ink_redrawn,
    }
    worse = {k: (round(now[k], 3), floor) for k, floor in FLOORS.items() if now[k] < floor}
    assert not worse, f"benchmark got worse (now, floor): {worse}"
