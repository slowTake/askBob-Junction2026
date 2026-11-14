"""Tidying a sketch plan: straight walls, closed corners, openings on their walls.

The page is 1000 x 1000 px in every test, so the join tolerance is
JOIN_SHARE (1 %) x 1000 = 10 px and an opening reaches walls up to 20 px away.
Expected values are worked out by hand next to each assertion.
"""

from app.domain.sketch import Door, Note, Plan, Room, Wall, Window
from app.domain.sketch_tidy import cluster, tidy

PAGE = 1000.0


def _tidy(**parts: object) -> Plan:
    return tidy(Plan(**parts), PAGE, PAGE)  # type: ignore[arg-type]


def test_cluster_groups_values_within_the_tolerance_of_the_first() -> None:
    # 96 and 100 are 4 apart (<= 10): one group, mean 98. 400 stands alone.
    assert cluster([400, 100, 96], 10) == {96: 98, 100: 98, 400: 400}
    # 0, 9, 18: 18 - 0 = 18 > 10, so 18 starts a new group: {0, 9} -> 4.5.
    assert cluster([0, 9, 18], 10) == {0: 4.5, 9: 4.5, 18: 18}
    assert cluster([], 10) == {}


def test_a_nearly_horizontal_wall_becomes_horizontal_at_its_mean_height() -> None:
    plan = _tidy(walls=(Wall((0, 100), (500, 104), outer=True),))
    # 4 px over 500 px is 0.46 degrees (< 8): y = (100 + 104) / 2 = 102.
    assert plan.walls == (Wall((0, 102), (500, 102), outer=True),)


def test_a_nearly_vertical_wall_becomes_vertical() -> None:
    plan = _tidy(walls=(Wall((300, 0), (310, 600), outer=False),))
    # 10 px over 600 px is 0.95 degrees: x = (300 + 310) / 2 = 305.
    assert plan.walls == (Wall((305, 0), (305, 600), outer=False),)


def test_ends_that_almost_meet_are_joined_into_a_corner() -> None:
    plan = _tidy(
        walls=(
            Wall((100, 100), (500, 100), outer=True),
            Wall((504, 96), (506, 400), outer=True),
        )
    )
    # Vertical line x = 505. x values: 100, 500, 505 -> {100}, {500, 505} = 502.5.
    # y values: line 100, ends 96 and 400 -> {96, 100} = 98, {400}.
    assert plan.walls == (
        Wall((100, 98), (502.5, 98), outer=True),
        Wall((502.5, 98), (502.5, 400), outer=True),
    )


def test_a_diagonal_wall_stays_diagonal() -> None:
    plan = _tidy(walls=(Wall((100, 100), (300, 300), outer=False),))
    assert plan.walls == (Wall((100, 100), (300, 300), outer=False),)  # 45 degrees


def test_a_wall_shorter_than_the_join_tolerance_disappears() -> None:
    # Ends 100 and 106 are one group (mean 103): the wall has no length left.
    assert _tidy(walls=(Wall((100, 100), (106, 100), outer=True),)).walls == ()


def test_a_wall_drawn_twice_is_kept_once_and_outer_wins() -> None:
    plan = _tidy(
        walls=(
            Wall((100, 100), (500, 100), outer=False),
            Wall((101, 101), (499, 99), outer=True),
        )
    )
    # x: {100, 101} = 100.5, {499, 500} = 499.5; y: both lines at 100.
    assert plan.walls == (Wall((100.5, 100), (499.5, 100), outer=True),)


def test_a_door_is_put_onto_its_wall() -> None:
    plan = _tidy(
        walls=(Wall((0, 100), (1000, 100), outer=True),),
        doors=(Door((200, 106), (260, 108), hinge_at_a=True, toward=(230, 150)),),
    )
    # The door's middle (230, 107) is 7 px from the wall: projected onto y = 100.
    assert plan.doors == (Door((200, 100), (260, 100), hinge_at_a=True, toward=(230, 150)),)


def test_an_opening_past_the_wall_end_is_clipped_to_the_wall() -> None:
    plan = _tidy(
        walls=(Wall((0, 100), (300, 100), outer=True),),
        windows=(Window((280, 100), (330, 100)),),
    )
    # Middle (305, 100) is 5 px past the end (<= 20): 330 is clipped to 300.
    assert plan.windows == (Window((280, 100), (300, 100)),)


def test_an_opening_without_a_wall_nearby_is_only_straightened() -> None:
    plan = _tidy(
        walls=(Wall((0, 100), (1000, 100), outer=True),),
        windows=(Window((500, 500), (560, 503)),),  # 400 px from the wall
        doors=(Door((400, 90), (400, 110), hinge_at_a=False, toward=(420, 100)),),
    )
    assert plan.windows == (Window((500, 501.5), (560, 501.5)),)  # y = (500 + 503) / 2
    # Across the wall, not along it: left where it is (already vertical).
    assert plan.doors == (Door((400, 90), (400, 110), hinge_at_a=False, toward=(420, 100)),)


def test_room_outlines_snap_to_the_walls_and_labels_and_notes_stay() -> None:
    plan = _tidy(
        walls=(
            Wall((100, 100), (500, 100), outer=True),
            Wall((504, 96), (506, 400), outer=True),
        ),
        rooms=(Room("kitchen", (300, 250), ((98, 98), (502, 99), (503, 401))),),
        notes=(Note("N", (900, 900)),),
    )
    # Groups as in the corner test: x 100 and 502.5, y 98 and 400.
    assert plan.rooms == (Room("kitchen", (300, 250), ((100, 98), (502.5, 98), (502.5, 400))),)
    assert plan.notes == (Note("N", (900, 900)),)
