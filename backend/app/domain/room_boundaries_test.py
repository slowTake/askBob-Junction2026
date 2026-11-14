from app.domain.room_boundaries import holds_one_room

ROOM = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]


def test_one_room_and_neighbours_outside() -> None:
    assert holds_one_room(ROOM, (50, 50), [(150, 50), (50, 150)])
    assert holds_one_room(ROOM, (50, 50), [])


def test_an_apartment_boundary_cannot_be_one_of_its_rooms() -> None:
    assert not holds_one_room(ROOM, (25, 50), [(75, 50)])


def test_an_outline_around_another_room_is_rejected() -> None:
    assert not holds_one_room(ROOM, (150, 50), [])


def test_empty_and_degenerate_polygons_cannot_outline_a_room() -> None:
    assert not holds_one_room([], (50, 50), [])
    assert not holds_one_room([(0, 0), (100, 0)], (50, 50), [])
