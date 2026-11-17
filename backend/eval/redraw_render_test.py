import numpy as np

from eval.redraw_render import (
    MaskScore,
    fixture_mask,
    mask_scores,
    near_share,
    opening_mask,
    wall_mask,
)
from eval.redraw_sheet import Fixture, Opening, Wall


def _mask(width: int, height: int, *pixels: tuple[int, int]) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    for x, y in pixels:
        mask[y, x] = True
    return mask


def test_walls_are_filled_where_their_outline_is() -> None:
    band = Wall(((10.0, 10.0), (20.0, 10.0), (20.0, 12.0), (10.0, 12.0)))
    mask = wall_mask([band], 40, 30)
    assert mask.shape == (30, 40)
    assert mask[11, 15]  # inside the band (row y, column x)
    assert not mask[15, 15]  # 3 px below it
    assert not mask[11, 25]  # 5 px past its end


def test_where_walls_overlap_the_page_stays_filled() -> None:
    # Two 10 x 10 squares overlapping on x 5..10, y 5..10 (a T-junction's shared corner):
    # (7, 7) lies in both, so it is wall.
    a = Wall(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)))
    b = Wall(((5.0, 5.0), (15.0, 5.0), (15.0, 15.0), (5.0, 15.0)))
    assert wall_mask([a, b], 20, 20)[7, 7]


def test_a_wall_off_the_page_is_clipped_not_an_error() -> None:
    mask = wall_mask([Wall(((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)))], 10, 10)
    assert mask[0, 0] and not mask[9, 9]


def test_near_share_counts_pixels_within_the_tolerance() -> None:
    # One source pixel 3 px from the only target pixel: within 3, not within 2.
    source, target = _mask(10, 10, (5, 5)), _mask(10, 10, (5, 8))
    assert near_share(source, target, 3) == 1.0
    assert near_share(source, target, 2) == 0.0


def test_near_share_is_the_share_of_source_pixels() -> None:
    # (0, 0) is 1 px from the target at (0, 1); (0, 9) is 8 px away: one of two.
    source, target = _mask(10, 10, (0, 0), (0, 9)), _mask(10, 10, (0, 1))
    assert near_share(source, target, 1) == 0.5


def test_near_share_uses_straight_line_distance() -> None:
    # (0, 0) to (3, 4) is 5 px: within 5, not within 4.9 (a city-block distance would be 7).
    source, target = _mask(10, 10, (0, 0)), _mask(10, 10, (3, 4))
    assert near_share(source, target, 5) == 1.0
    assert near_share(source, target, 4.9) == 0.0


def test_nothing_to_cover_is_fully_covered_and_nothing_covers_nothing() -> None:
    empty, one = _mask(5, 5), _mask(5, 5, (2, 2))
    assert near_share(empty, one, 1) == 1.0
    assert near_share(one, empty, 1) == 0.0


def test_a_redraw_shifted_by_the_tolerance_still_scores_full_marks() -> None:
    # Truth: a 10 px line on row 5. Redraw: the same line on row 7, 2 px off.
    truth = _mask(20, 20, *[(x, 5) for x in range(5, 15)])
    redraw = _mask(20, 20, *[(x, 7) for x in range(5, 15)])
    assert mask_scores(redraw, truth, 2) == MaskScore(recall=1.0, precision=1.0)
    assert mask_scores(redraw, truth, 1) == MaskScore(recall=0.0, precision=0.0)


def test_extra_redraw_lowers_precision_and_missing_redraw_lowers_recall() -> None:
    # Truth: x 0..9 on row 5. Redraw: x 0..4 on row 5 plus 15 pixels on row 15, 10 px
    # from any truth. Within 1 px the redraw covers truth x 0..5 (x 5 is 1 px from x 4):
    # recall 6/10. Its row-5 pixels lie on the truth, the row-15 ones don't: 5/20.
    truth = _mask(20, 20, *[(x, 5) for x in range(10)])
    redraw = _mask(20, 20, *[(x, 5) for x in range(5)], *[(x, 15) for x in range(15)])
    score = mask_scores(redraw, truth, 1)
    assert score == MaskScore(recall=0.6, precision=0.25)
    # F1 = 2 * 0.6 * 0.25 / 0.85 = 0.3 / 0.85 = 6/17.
    assert abs(score.f1 - 6 / 17) < 1e-12


def test_f1_of_nothing_right_is_zero() -> None:
    assert MaskScore(recall=0.0, precision=0.0).f1 == 0.0


def test_a_window_is_drawn_as_its_line_on_the_wall() -> None:
    window = Opening("window", (10.0, 20.0), (40.0, 20.0))
    mask = opening_mask([window], 60, 40)
    assert mask[20, 10] and mask[20, 25] and mask[20, 40]  # the line, ends included
    assert mask.sum() == 31  # x 10..40 on row 20, 1 px wide


def test_a_window_with_a_frame_is_drawn_as_the_frame() -> None:
    frame = ((10.0, 16.0), (40.0, 16.0), (40.0, 20.0), (10.0, 20.0))
    mask = opening_mask([Opening("window", (10.0, 20.0), (40.0, 20.0), frame=frame)], 60, 40)
    assert mask[16, 25] and mask[20, 25] and mask[18, 10] and mask[18, 40]  # its four sides
    assert not mask[18, 25]  # not the glass
    assert mask.sum() == 2 * 31 + 2 * 3  # rows 16 and 20 (x 10..40), columns 10 and 40 between


def test_a_door_is_drawn_as_its_leaf_and_swing() -> None:
    # Gap (10, 20)..(30, 20), hinge at (10, 20), opening downwards (y > 20): the leaf goes
    # from the hinge 20 px down to (10, 40); the arc, radius 20 round the hinge, from there
    # to the gap's free end (30, 20).
    door = Opening("door", (10.0, 20.0), (30.0, 20.0), hinge=(10.0, 20.0), toward=(20.0, 30.0))
    mask = opening_mask([door], 60, 60)
    assert mask[30, 10] and mask[40, 10]  # on the leaf
    # 45 degrees on the arc: (10 + 20 cos 45, 20 + 20 sin 45) = (24.1, 34.1)
    assert mask[34, 24]
    assert not mask[20, 20]  # the gap itself is not drawn
    assert not mask[10, 10] and not mask[30, 20]  # not above the wall, not inside the swing


def test_a_door_without_a_swing_is_drawn_as_its_line() -> None:
    door = Opening("door", (10.0, 20.0), (30.0, 20.0))
    assert opening_mask([door], 60, 40).sum() == 21  # x 10..30 on row 20


def test_a_fixture_is_drawn_as_its_closed_outline() -> None:
    square = Fixture(((10.0, 10.0), (19.0, 10.0), (19.0, 19.0), (10.0, 19.0)))
    mask = fixture_mask([square], 40, 40)
    assert mask[10, 15] and mask[15, 10] and mask[19, 15] and mask[15, 19]  # its four sides
    assert not mask[15, 15]  # not filled
    assert mask.sum() == 36  # a 10 x 10 outline, 1 px: 4 x 10 - 4 corners
