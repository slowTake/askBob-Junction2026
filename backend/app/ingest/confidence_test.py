import numpy as np
import pytest

from app.domain.redraw_confidence import PARTS, PartScore, Shape, score
from app.ingest.confidence import page_ink, redraw_confidence, score_redraw
from app.ingest.ink import separate_colours

W, H = 482, 507  # the benchmark page: the tolerance is 2 px
TOL = 2.0
# A band x 20..180, y 90..110, edges included when filled: 161 x 21 = 3381 px.
BAND = ((20, 90), (180, 90), (180, 110), (20, 110))
WALL = Shape("walls", BAND)
NOTHING = PartScore(count=0, drawn_px=0, on_ink=1.0, ink_covered=0.0)


def blank() -> np.ndarray:
    return np.zeros((H, W), dtype=bool)


def band_ink() -> np.ndarray:
    ink = blank()
    ink[90:111, 20:181] = True
    return ink


def box(polygon: tuple[tuple[float, float], ...]) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def test_a_redraw_of_the_ink_itself_scores_one() -> None:
    c = redraw_confidence(band_ink(), [WALL], TOL)
    assert (c.score, c.covered, c.on_ink, c.ink_px) == (1.0, 1.0, 1.0, 3381)
    assert c.parts["walls"] == PartScore(count=1, drawn_px=3381, on_ink=1.0, ink_covered=1.0)
    assert all(c.parts[p] == NOTHING for p in PARTS if p != "walls")
    assert tuple(c.parts) == PARTS  # every part is listed, in the view's order
    assert c.missed == () and c.added == ()


def test_ink_left_out_is_missed_and_marked() -> None:
    ink = band_ink()
    ink[300:310, 300:310] = True  # 100 px, far from the band
    c = redraw_confidence(ink, [WALL], TOL)
    covered = 3381 / 3481
    assert (c.covered, c.on_ink) == (pytest.approx(covered), 1.0)
    assert c.score == pytest.approx(score(covered, 1.0))
    assert c.parts["walls"].ink_covered == pytest.approx(covered)
    [mark] = c.missed
    # The patch is outlined with the tolerance round it: 300..309 grown by 2 px each way.
    assert mark.px == 100 and box(mark.polygon) == (298, 298, 311, 311)
    assert c.added == ()


def test_a_wall_on_blank_paper_is_added_and_marked() -> None:
    extra = Shape("walls", ((300, 300), (309, 300), (309, 309), (300, 309)))
    c = redraw_confidence(band_ink(), [WALL, extra], TOL)
    on_ink = 3381 / 3481
    assert (c.covered, c.on_ink) == (1.0, pytest.approx(on_ink))
    assert c.parts["walls"] == PartScore(1 + 1, 3481, pytest.approx(on_ink), 1.0)  # type: ignore[arg-type]
    [mark] = c.added
    assert mark.px == 100 and box(mark.polygon) == (298, 298, 311, 311)
    assert c.missed == ()


def test_the_tolerance_forgives_two_pixels_not_three() -> None:
    two_down = Shape("walls", ((20, 92), (180, 92), (180, 112), (20, 112)))
    c = redraw_confidence(band_ink(), [two_down], TOL)
    assert (c.covered, c.on_ink) == (1.0, 1.0)
    three_down = Shape("walls", ((20, 93), (180, 93), (180, 113), (20, 113)))
    c = redraw_confidence(band_ink(), [three_down], TOL)
    # Ink row 90 is 3 px from the redraw's first row 93: one row of 161 px missed, and
    # the redraw's row 113 is 3 px from the ink's last row 110: one row added.
    assert c.covered == pytest.approx(3220 / 3381) and c.on_ink == pytest.approx(3220 / 3381)
    assert [m.px for m in c.missed] == [161] and [m.px for m in c.added] == [161]


def test_nothing_to_compare_scores_one_and_an_undrawn_page_zero() -> None:
    c = redraw_confidence(blank(), [], TOL)
    assert (c.score, c.covered, c.on_ink, c.ink_px) == (1.0, 1.0, 1.0, 0)
    c = redraw_confidence(band_ink(), [], TOL)
    assert (c.score, c.covered, c.on_ink) == (0.0, 0.0, 1.0)
    assert [m.px for m in c.missed] == [3381]


def test_each_part_is_scored_on_its_own() -> None:
    ink = band_ink()
    ink[146:154, 95:105] = True  # a printed name: 10 x 8 = 80 px
    # The name drawn in the room size: (95.662, 146.385)-(104.338, 153.615), filled from
    # the rounded corners (96, 146)-(104, 154): 9 x 9 = 81 px, all within 2 px of the ink.
    name = Shape(
        "rooms", ((95.662, 146.385), (104.338, 146.385), (104.338, 153.615), (95.662, 153.615))
    )
    c = redraw_confidence(ink, [WALL, name], TOL)
    assert (c.covered, c.on_ink, c.score) == (1.0, 1.0, 1.0)
    assert c.parts["rooms"] == PartScore(1, 81, 1.0, pytest.approx(80 / 3461))  # type: ignore[arg-type]
    assert c.parts["walls"] == PartScore(1, 3381, 1.0, pytest.approx(3381 / 3461))  # type: ignore[arg-type]


def test_marks_are_the_largest_patches_first_and_capped() -> None:
    ink = blank()
    ink[10:12, 10:12] = True  # 4 px
    ink[100:103, 100:103] = True  # 9 px
    ink[200:204, 200:204] = True  # 16 px
    c = redraw_confidence(ink, [], TOL, cap=2)
    assert [m.px for m in c.missed] == [16, 9]


def test_the_page_ink_is_its_line_work_and_its_red_annotations() -> None:
    rgb = np.full((8, 12, 3), 255, dtype=np.uint8)
    rgb[3, :] = (0, 0, 0)  # a wall line: 12 px of ink
    rgb[6, 2:7] = (220, 40, 40)  # a red height label: 5 px, an annotation
    rgb[0:2, 8:12] = (255, 240, 120)  # a yellow fill: paper to the redraw
    layers = separate_colours(rgb)
    assert page_ink(layers).sum() == 12 + 5
    # A wall over the line and a height over the label account for all of it; the
    # tolerance on a 12 px page is 2 / 482 x 12 = 0.05 px, so the match is exact.
    wall = Shape("walls", ((0, 3), (11, 3), (11, 3), (0, 3)))
    height = Shape("heights", ((2, 6), (6, 6), (6, 6), (2, 6)))
    c = score_redraw(layers, [wall, height])
    assert (c.covered, c.on_ink) == (1.0, 1.0)
    assert c.parts["heights"].ink_covered == pytest.approx(5 / 17)
    # Without the height, the red label is missed ink.
    c = score_redraw(layers, [wall])
    assert c.covered == pytest.approx(12 / 17) and [m.px for m in c.missed] == [5]
