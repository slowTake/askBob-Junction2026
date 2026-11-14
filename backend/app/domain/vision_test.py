from app.domain.vision import (
    Finding,
    long_side_px,
    object_findings,
    outline_for,
    parse,
    unlabelled_rooms,
    wall_findings,
)


def _square(x: float, y: float, side: float) -> list[list[float]]:
    return [[x, y], [x + side, y], [x + side, y + side], [x, y + side]]


RESULT = {
    "rooms": [
        {"class": "Kitchen", "polygon": _square(0, 0, 100)},
        {"class": "Bath", "polygon": _square(200, 0, 50)},
        {"class": "Undefined", "polygon": _square(400, 0, 80)},
        {"class": "Outdoor", "polygon": _square(600, 0, 60)},
    ],
    "walls": [_square(0, 100, 10), [[1, 1], [2, 2]]],  # the second is not a polygon
    "objects": [
        {"class": "Door", "polygon": [[10, 95], [50, 95], [50, 105], [10, 105]]},
        {"class": "Window", "polygon": _square(150, 0, 5)},
        {"class": "Sink", "polygon": _square(20, 20, 10)},  # inside the kitchen
        {"class": "Sink", "polygon": _square(210, 10, 10)},  # inside the bath
        {"class": "Toilet", "polygon": _square(220, 30, 10)},
        {"class": "Bathtub", "polygon": _square(230, 5, 10)},
        {"class": "Closet", "polygon": _square(300, 300, 10)},
        {"class": "Spaceship", "polygon": _square(0, 0, 1)},  # unknown class: dropped
    ],
}


def test_parse_drops_malformed_entries() -> None:
    parsed = parse(RESULT)
    assert len(parsed.walls) == 1  # [[1,1],[2,2]] has two points: not an outline
    assert "Spaceship" not in [o.cls for o in parsed.objects]


def test_parse_tolerates_garbage() -> None:
    parsed = parse({"rooms": "nope", "objects": [{"class": "Door"}], "walls": None})
    assert (parsed.rooms, parsed.walls, parsed.objects) == ([], [], [])


def test_doors_windows_and_fixture_subtypes() -> None:
    found = {(f.kind, f.properties.get("subtype")) for f in object_findings(parse(RESULT))}
    assert ("door", None) in found
    assert ("window", None) in found
    assert ("fixture", "wc") in found
    assert ("fixture", "bathtub") in found


def test_a_sink_in_a_kitchen_is_a_sink_elsewhere_a_washbasin() -> None:
    sinks = [
        f.properties["subtype"]
        for f in object_findings(parse(RESULT))
        if f.properties.get("subtype") in ("sink", "washbasin")
    ]
    assert sorted(sinks) == ["sink", "washbasin"]


def test_other_objects_are_untyped_fixtures_named_by_class() -> None:
    closet = next(f for f in object_findings(parse(RESULT)) if f.properties.get("object"))
    assert closet.kind == "fixture"
    assert closet.properties == {"object": "closet", "model_class": "Closet"}


def test_findings_are_marked_as_model_output() -> None:
    for f in object_findings(parse(RESULT)):
        assert isinstance(f, Finding)
        assert 0 < f.confidence < 1


def test_walls_keep_their_outline() -> None:
    walls = wall_findings(parse(RESULT))
    assert [w.kind for w in walls] == ["wall"]
    assert walls[0].polygon == [(0, 100), (10, 100), (10, 110), (0, 110)]


def test_outline_for_a_label_is_the_smallest_room_around_it() -> None:
    rooms = parse(
        {"rooms": [
            {"class": "Undefined", "polygon": _square(0, 0, 500)},
            {"class": "Bed Room", "polygon": _square(100, 100, 50)},
        ]}
    ).rooms  # fmt: skip
    assert outline_for((120, 120), rooms) == [(100, 100), (150, 100), (150, 150), (100, 150)]
    assert outline_for((10, 10), rooms) == [(0, 0), (500, 0), (500, 500), (0, 500)]
    assert outline_for((900, 900), rooms) is None


def test_unlabelled_rooms_get_a_category_but_undefined_ones_are_skipped() -> None:
    rooms = parse(RESULT).rooms
    found = unlabelled_rooms(rooms, label_points=[(50, 50)], min_area_px=100)
    # The kitchen holds a label, so OCR names it; Undefined is skipped; Bath and
    # Outdoor are new rooms.
    assert sorted(f.properties["category"] for f in found) == ["bathroom", "outdoor"]
    outdoor = next(f for f in found if f.properties["category"] == "outdoor")
    assert outdoor.properties["outdoor"] is True
    assert all(f.kind == "room" for f in found)


def test_tiny_unlabelled_rooms_are_noise() -> None:
    rooms = parse({"rooms": [{"class": "Bath", "polygon": _square(0, 0, 5)}]}).rooms
    assert unlabelled_rooms(rooms, label_points=[], min_area_px=100) == []  # 25 px² < 100


def test_long_side_of_a_door_box() -> None:
    assert long_side_px([(10, 95), (50, 95), (50, 105), (10, 105)]) == 40  # 50 - 10
