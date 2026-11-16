import json

import numpy as np
import pytest

from app.domain.tokens import Word
from eval.redraw_bench import (
    IMAGE,
    OCR,
    VISION,
    page,
    read_words,
    recorded_vision,
    recorded_words,
    redraw,
    report,
    table,
)
from eval.redraw_bench import TRUTH as TRUTH_FILE
from eval.redraw_render import wall_mask
from eval.redraw_sheet import Opening, Room, Sheet, Text, Wall, load_sheet

W, H = 482, 507  # the benchmark page: tolerances are 2 px (walls, ink) and 4 px (positions)

TRUTH = Sheet(
    walls=(Wall(((20, 90), (180, 90), (180, 110), (20, 110))),),
    openings=(Opening("door", (50, 50), (90, 50)),),
    rooms=(Room("mh", (100, 150)),),
    texts=(Text("5,341", "dimension", (100, 30)),),
)


def test_a_redraw_equal_to_the_truth_scores_everything() -> None:
    ink = wall_mask(TRUTH.walls, W, H)
    r = report(TRUTH, TRUTH, ink, W, H)
    assert r.wall_tolerance_px == pytest.approx(2.0)  # 2/482 of a 482 px page
    assert r.position_tolerance_px == pytest.approx(4.0)
    assert (r.walls.recall, r.walls.precision) == (1.0, 1.0)
    assert r.openings.found.matched == 1
    assert r.openings.swings_checked == 0  # the truth door gives no hinge
    assert r.rooms.named.matched == 1 and r.rooms.outlined == 0  # no outlines to compare
    t = r.texts
    assert (t.found.matched, t.exact, t.digits, t.kind_ok, t.rotation_ok) == (1, 1, 1, 1, 1)
    # The ink is exactly the truth walls: all of them found, none of it elsewhere.
    assert (r.ink_finds_walls, r.ink_off_walls) == (1.0, 0.0)
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
    ink = wall_mask(TRUTH.walls, W, H)
    ink[300:310, 300:310] = True  # 100 px, far from the wall
    r = report(TRUTH, TRUTH, ink, W, H)
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


def test_positions_count_within_four_pixels() -> None:
    near = Sheet(texts=(Text("5,341", "dimension", (103, 30)),))  # 3 px off
    far = Sheet(texts=(Text("5,341", "dimension", (105, 30)),))  # 5 px off
    ink = np.zeros((H, W), dtype=bool)
    assert report(near, TRUTH, ink, W, H).texts.found.matched == 1
    assert report(far, TRUTH, ink, W, H).texts.found.matched == 0


def test_the_table_shows_the_numbers() -> None:
    text = table(report(TRUTH, TRUTH, wall_mask(TRUTH.walls, W, H), W, H))
    assert "recall 100.0%" in text and "off walls   0.0%" in text and "on ink 100.0%" in text


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
# traced walls (D-053); they are recorded values, not worked out by hand, and stop a
# change from making the redraw of colorful-34 worse. A PR that improves a number raises
# its floor; one that has to lower a floor says why in its decision.
FLOORS = {
    "walls recall": 0.964,  # ratios are rounded down: 0.96488 recorded
    # D-053 lowered this from 0.969: 3 thick walls became the whole wall network, with
    # fixtures and handwriting that touch the walls (0.80495 recorded).
    "walls precision": 0.804,
    "openings found": 0,
    "rooms named": 3,
    "rooms outlined": 3,
    "texts found": 25,
    "texts precision": 0.862,  # D-052: the stove is no longer drawn as "1281"; 25/29
    "texts exact": 11,
    "texts digits": 13,
    "texts kind": 16,  # #36: decimal-comma dimensions and h-heights have their kind
    "redraw on ink": 0.998,  # 0.99822 recorded
    "ink redrawn": 0.795,  # 0.79521 recorded (D-053)
}


def test_the_benchmark_does_not_get_worse() -> None:
    layers, _ = page(IMAGE)
    height, width = layers.ink_page.shape
    ocr, vision = (json.loads(p.read_text(encoding="utf-8")) for p in (OCR, VISION))
    truth = load_sheet(json.loads(TRUTH_FILE.read_text(encoding="utf-8")), width, height)
    sheet = redraw(layers.ink_page, read_words(layers, ocr), recorded_vision(vision))
    r = report(sheet, truth, layers.ink, width, height)
    now = {
        "walls recall": r.walls.recall,
        "walls precision": r.walls.precision,
        "openings found": r.openings.found.matched,
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
