"""Room outlines from a line network (D-024). Expected values are worked out by hand."""

import pytest
from shapely.geometry import LineString, Polygon

from app.domain.room_faces import faces_from_lines, room_outlines, to_wall_face


def _box(x0: float, y0: float, x1: float, y1: float) -> list[LineString]:
    return [
        LineString([(x0, y0), (x1, y0)]),
        LineString([(x1, y0), (x1, y1)]),
        LineString([(x1, y1), (x0, y1)]),
        LineString([(x0, y1), (x0, y0)]),
    ]


def _area(outline: list[tuple[float, float]] | None) -> float:
    assert outline is not None
    return round(Polygon(outline).area)


def test_two_rooms_sharing_a_wall_line() -> None:
    # 0..100 x 0..50 split at x=60: rooms of 60*50 = 3000 and 40*50 = 2000 px².
    lines = [*_box(0, 0, 100, 50), LineString([(60, 0), (60, 50)])]
    assert sorted(round(f.area) for f in faces_from_lines(lines, snap_px=2)) == [2000, 3000]


def test_lines_that_stop_just_short_still_close_a_room() -> None:
    # The right side ends 2 px below the top line: extending ends by 3 px closes it.
    lines = [
        LineString([(0, 0), (40, 0)]),
        LineString([(40, 2), (40, 40)]),
        LineString([(40, 40), (0, 40)]),
        LineString([(0, 40), (0, 0)]),
    ]
    assert [round(f.area) for f in faces_from_lines(lines, snap_px=3)] == [1600]


def test_each_label_gets_the_room_around_it() -> None:
    lines = [*_box(0, 0, 100, 50), LineString([(60, 0), (60, 50)])]
    left, right, outside = room_outlines(
        lines, [(30, 25), (80, 25), (500, 500)], min_area_px=100, min_width_px=4
    )
    assert (_area(left), _area(right), outside) == (3000, 2000, None)


def test_wall_interiors_and_hatching_are_not_rooms() -> None:
    # A double-line wall 6 px thick around a 100 x 100 room, hatched inside the wall:
    # the wall's thin ring and the hatch cells are dropped, the room stays.
    lines = [*_box(0, 0, 112, 112), *_box(6, 6, 106, 106)]
    lines += [LineString([(x, 0), (x + 6, 6)]) for x in range(10, 100, 12)]
    [room] = room_outlines(lines, [(56, 56)], min_area_px=500, min_width_px=8)
    assert _area(room) == 10000  # 100 x 100 inside the wall


def test_a_label_inside_furniture_goes_to_the_room_around_it() -> None:
    # A bathtub (10..40 x 10..30) inside a room 100 x 80; the room's number is written
    # inside the tub's outline. The room (8000) gets it, not the tub (600).
    lines = [*_box(0, 0, 100, 80), *_box(10, 10, 40, 30)]
    [room] = room_outlines(lines, [(25, 20)], min_area_px=100, min_width_px=4)
    assert _area(room) == 8000


def test_a_bigger_room_never_takes_its_neighbours_label() -> None:
    lines = [*_box(0, 0, 100, 50), LineString([(60, 0), (60, 50)])]
    left, right = room_outlines(lines, [(30, 25), (80, 25)], min_area_px=100, min_width_px=4)
    assert (_area(left), _area(right)) == (3000, 2000)


def test_a_counter_against_the_wall_is_part_of_the_kitchen() -> None:
    # Kitchen 100 x 80; a counter 40 x 15 closed against two walls. It touches only
    # the kitchen, so it is absorbed: 8000 px², not 8000 - 600.
    lines = [*_box(0, 0, 100, 80), LineString([(0, 15), (40, 15)]), LineString([(40, 15), (40, 0)])]
    [kitchen] = room_outlines(lines, [(60, 50)], min_area_px=500, min_width_px=4)
    assert _area(kitchen) == 8000


def test_a_face_between_two_rooms_stays_out_of_both() -> None:
    # A 10 x 10 face in the doorway between rooms touches both: left room 60*50 minus
    # its 5 x 10 half = 2950; right 40*50 minus the other half = 1950.
    lines = [
        *_box(0, 0, 100, 50),
        LineString([(60, 0), (60, 20)]),
        LineString([(60, 30), (60, 50)]),
        *_box(55, 20, 65, 30),
    ]
    left, right = room_outlines(lines, [(25, 25), (85, 25)], min_area_px=200, min_width_px=4)
    assert (_area(left), _area(right)) == (2950, 1950)


def test_the_page_around_the_building_doesnt_swallow_its_rooms() -> None:
    # A sheet frame around a building with two rooms: the face between frame and
    # building is page, not one room around both.
    lines = [*_box(0, 0, 1000, 1000), *_box(100, 100, 300, 200)]
    lines.append(LineString([(200, 100), (200, 200)]))
    a, b = room_outlines(
        lines, [(150, 150), (250, 150)], min_area_px=500, min_width_px=4, max_area_px=50_000
    )
    assert (_area(a), _area(b)) == (10000, 10000)


def test_no_lines_no_rooms() -> None:
    assert room_outlines([], [(1, 1)], min_area_px=1, min_width_px=1) == [None]


def test_to_wall_face_moves_the_outline_out_and_keeps_corners() -> None:
    # A 100 x 50 outline moved 2 px out with mitred corners: 104 x 54 = 5616 px².
    out = to_wall_face([(0, 0), (100, 0), (100, 50), (0, 50)], edge_px=2)
    assert round(Polygon(out).area) == pytest.approx(5616)
