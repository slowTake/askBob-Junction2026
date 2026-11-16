from eval.redraw_score import (
    Counts,
    OpeningScore,
    RoomScore,
    TextScore,
    match_openings,
    match_rooms,
    match_texts,
)
from eval.redraw_sheet import Opening, Room, Text

TOL = 3.0


def test_counts_give_precision_recall_and_f1() -> None:
    # 3 of 4 predictions right, 3 of 5 truths found: 0.75, 0.6, F1 = 0.9 / 1.35 = 2/3.
    c = Counts(predicted=4, truth=5, matched=3)
    assert (c.precision, c.recall) == (0.75, 0.6)
    assert abs(c.f1 - 2 / 3) < 1e-12


def test_counts_of_nothing_are_perfect_and_finding_nothing_is_zero() -> None:
    assert Counts(0, 0, 0).f1 == 1.0
    assert (Counts(0, 3, 0).precision, Counts(0, 3, 0).recall, Counts(0, 3, 0).f1) == (1, 0, 0)


DOOR = Opening("door", (10.0, 10.0), (20.0, 10.0), hinge=(10.0, 10.0), toward=(15.0, 20.0))
WINDOW = Opening("window", (40.0, 10.0), (50.0, 10.0))


def test_openings_match_by_kind_and_middle() -> None:
    # The door drawn from the other end, 1 px off: middle (16, 11) vs (15, 10), √2 away.
    # Hinge (11, 11) is √2 from (10, 10); toward (15, 25) is on the same side of the
    # wall as (15, 20) (both below y = 10): its swing is right.
    door = Opening("door", (21.0, 11.0), (11.0, 11.0), hinge=(11.0, 11.0), toward=(15.0, 25.0))
    window = Opening("window", (41.0, 10.0), (51.0, 10.0))
    # A window where the door is: wrong kind for the door, too far from the window.
    stray = Opening("window", (10.0, 10.0), (20.0, 10.0))
    score = match_openings([door, window, stray], [DOOR, WINDOW], TOL)
    assert score == OpeningScore(Counts(3, 2, 2), swings_checked=1, swings_ok=1)


def test_a_door_hinged_at_the_wrong_end_or_opening_the_wrong_way_is_found_but_not_right() -> None:
    wrong_end = Opening("door", (10.0, 10.0), (20.0, 10.0), hinge=(20.0, 10.0), toward=(15.0, 20.0))
    # (15, 0) is above the wall; the truth swings below it.
    wrong_side = Opening("door", (10.0, 10.0), (20.0, 10.0), hinge=(10.0, 10.0), toward=(15.0, 0.0))
    no_swing = Opening("door", (10.0, 10.0), (20.0, 10.0))
    for door in (wrong_end, wrong_side, no_swing):
        assert match_openings([door], [DOOR], TOL) == OpeningScore(Counts(1, 1, 1), 1, 0)


def test_one_truth_is_found_once() -> None:
    assert match_openings([WINDOW, WINDOW], [WINDOW], TOL).found == Counts(2, 1, 1)


def test_an_opening_further_than_the_tolerance_is_not_found() -> None:
    # Middle (15, 14) is 4 px from (15, 10).
    moved = Opening("window", (10.0, 14.0), (20.0, 14.0))
    truth = Opening("window", (10.0, 10.0), (20.0, 10.0))
    assert match_openings([moved], [truth], TOL).found == Counts(1, 1, 0)


def _square(x0: float, y0: float, x1: float, y1: float) -> tuple[tuple[float, float], ...]:
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


KITCHEN = Room("keittiö", (25.0, 25.0), _square(0, 0, 50, 50))
BED_1 = Room("mh", (75.0, 25.0), _square(50, 0, 100, 50))
BED_2 = Room("mh", (25.0, 75.0), _square(0, 50, 50, 100))


def test_rooms_are_named_by_folded_name_inside_their_outline() -> None:
    # "Keittio" folds to "keittio" like "keittiö": named. Its outline 0..50 x 0..40 shares
    # 2000 of the truth's 2500 px²: IoU 0.8, outlined.
    kitchen = Room("Keittio", (30.0, 30.0), _square(0, 0, 50, 40))
    # Two "mh" in the first bedroom: one names it, the other has no bedroom left to name
    # (it is not inside the second one). No outline: named, not outlined.
    bed_a, bed_b = Room("MH", (80.0, 20.0)), Room("mh", (60.0, 10.0))
    # "wc" in the second bedroom: the wrong name.
    wc = Room("wc", (25.0, 75.0))
    score = match_rooms([kitchen, bed_a, bed_b, wc], [KITCHEN, BED_1, BED_2], TOL)
    assert score == RoomScore(named=Counts(4, 3, 2), outlined=1)


def test_rooms_of_the_same_name_are_matched_by_place() -> None:
    score = match_rooms([Room("mh", (70.0, 30.0)), Room("mh", (20.0, 80.0))], [BED_1, BED_2], TOL)
    assert score.named == Counts(2, 2, 2)


def test_an_outline_under_the_iou_threshold_is_not_outlined() -> None:
    # 0..50 x 0..30 shares 1500 of 2500 px²: IoU 0.6 < 0.7.
    kitchen = Room("keittiö", (25.0, 15.0), _square(0, 0, 50, 30))
    assert match_rooms([kitchen], [KITCHEN], TOL) == RoomScore(Counts(1, 1, 1), outlined=0)


def test_a_truth_room_without_an_outline_is_found_by_its_label() -> None:
    truth = Room("aula", (50.0, 50.0))
    # (52, 52) is 2.8 px away, within 3; (54, 50) is 4 px away.
    assert match_rooms([Room("aula", (52.0, 52.0))], [truth], TOL).named == Counts(1, 1, 1)
    assert match_rooms([Room("aula", (54.0, 50.0))], [truth], TOL).named == Counts(1, 1, 0)


def test_texts_are_found_by_place_then_checked_for_text_digits_kind_and_rotation() -> None:
    truth = [
        Text("5,341", "dimension", (10.0, 10.0)),
        Text("6,904", "dimension", (50.0, 50.0), rotation=90),
        Text("h1600", "height", (80.0, 80.0)),
    ]
    redraw = [
        # Spaces don't count: exact, same digits; read as "other": wrong kind.
        Text("5, 341", "other", (11.0, 11.0)),
        # A point for the comma: not exact, same digits; drawn level: wrong rotation.
        Text("6.904", "dimension", (50.0, 52.0)),
        # One digit misread: neither exact nor the same digits.
        Text("h1800", "height", (80.0, 80.0)),
        Text("noise", "other", (5.0, 90.0)),  # nothing written there
    ]
    assert match_texts(redraw, truth, TOL) == TextScore(
        found=Counts(4, 3, 3), exact=1, digits=2, kind_ok=2, rotation_ok=2
    )


def test_a_right_reading_wins_over_a_nearer_wrong_one() -> None:
    truth = [Text("12", "dimension", (10.0, 10.0))]
    redraw = [Text("13", "dimension", (10.0, 10.0)), Text("12", "dimension", (12.0, 10.0))]
    assert match_texts(redraw, truth, TOL).exact == 1


def test_digits_are_only_counted_for_texts_that_have_digits() -> None:
    # A north arrow's "N": exact, but there are no digits to agree on.
    score = match_texts([Text("n", "other", (0.0, 0.0))], [Text("N", "other", (0.0, 0.0))], TOL)
    assert (score.exact, score.digits) == (1, 0)
