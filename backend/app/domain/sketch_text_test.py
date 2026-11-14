"""No invented measurements: a number the model wrote must be on the page.

Page 1000 x 1000 px, so a written number must be confirmed by a word ingest read
within 5 % x 1000 = 50 px of where the model put it.
"""

from app.domain.sketch import Note, Plan, Room
from app.domain.sketch_text import Word, confirm_written, looks_like_measure

PAGE = 1000.0
NEAR = Word("3,5m", (90, 95, 130, 105))  # right at (100, 100)


def _check(words: list[Word], **parts: object) -> Plan:
    return confirm_written(Plan(**parts), words, PAGE, PAGE)  # type: ignore[arg-type]


def test_what_looks_like_a_measurement() -> None:
    for token in ("3.5", "3,5", "3600", "12m", "12m²", "4x3", "4\u00d73", "10'", '6"', "2.4m"):
        assert looks_like_measure(token), token
    # Room numbers and words are not measurements.
    for token in ("2", "12", "B", "bedroom", "WC"):
        assert not looks_like_measure(token), token


def test_text_without_digits_is_kept() -> None:
    plan = _check([], notes=(Note("N", (900, 50)), Note("closet", (10, 10))))
    assert plan.notes == (Note("N", (900, 50)), Note("closet", (10, 10)))


def test_a_number_nobody_read_on_the_page_is_dropped() -> None:
    assert _check([], notes=(Note("3.5 m", (100, 100)),)).notes == ()


def test_a_number_read_nearby_is_kept_exactly_as_the_model_wrote_it() -> None:
    # "3.5 m" and "3,5m" have the same digits, 35; the word box touches the point.
    plan = _check([NEAR], notes=(Note("3.5 m", (100, 100)),))
    assert plan.notes == (Note("3.5 m", (100, 100)),)


def test_the_same_number_far_away_or_another_number_nearby_does_not_count() -> None:
    far = Word("3.5", (500, 500, 520, 510))  # about 560 px away
    assert _check([far], notes=(Note("3.5 m", (100, 100)),)).notes == ()
    other = Word("2", (95, 95, 105, 105))
    assert _check([other], notes=(Note("12", (100, 100)),)).notes == ()


def test_a_word_just_inside_the_reach_counts() -> None:
    # Box edge at x 149.9: 49.9 px from (100, 100), within 50.
    edge = Word("35", (149.9, 90, 170, 110))
    assert _check([edge], notes=(Note("3.5", (100, 100)),)).notes == (Note("3.5", (100, 100)),)
    beyond = Word("35", (150.1, 90, 170, 110))  # 50.1 px
    assert _check([beyond], notes=(Note("3.5", (100, 100)),)).notes == ()


def test_room_names_lose_unconfirmed_measurements_but_keep_room_numbers() -> None:
    plan = _check(
        [],
        rooms=(
            Room("Bedroom 2", (100, 100), None),
            Room("Bedroom 3x4m", (300, 300), None),
            Room("12 m²", (500, 500), None),  # nothing left: the room has no name
        ),
    )
    assert plan.rooms == (
        Room("Bedroom 2", (100, 100), None),
        Room("Bedroom", (300, 300), None),
    )


def test_a_confirmed_measurement_stays_in_a_room_name() -> None:
    plan = _check(
        [Word("4.2", (95, 110, 115, 120))], rooms=(Room("Kitchen 4.2", (100, 100), None),)
    )
    assert plan.rooms == (Room("Kitchen 4.2", (100, 100), None),)
