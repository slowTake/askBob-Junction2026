import numpy as np
from shapely.geometry import MultiPolygon, Polygon

from app.shapes import ICONS, ROOMS, from_components, from_polygons


def test_from_polygons_names_classes_and_maps_back() -> None:
    door = np.array([[30, 60], [60, 60], [60, 66], [30, 66]])
    wall = np.array([[0, 0], [90, 0], [90, 6], [0, 6]])
    room = Polygon([(0, 0), (30, 0), (30, 30), (0, 30)])
    result = from_polygons(
        polygons=[wall, door],
        types=[{"type": "wall", "class": 2}, {"type": "icon", "class": 2}],
        room_polygons=[room],
        room_types=[{"type": "room", "class": ROOMS.index("Kitchen")}],
        scale=1.5,
        offset=(100, 200),
    )
    # (x / 1.5 + 100, y / 1.5 + 200): door corner (30, 60) -> (120, 240), by hand.
    assert result["objects"] == [
        {
            "class": "Door",
            "polygon": [[120.0, 240.0], [140.0, 240.0], [140.0, 244.0], [120.0, 244.0]],
        }
    ]
    assert result["walls"][0][1] == [160.0, 200.0]  # (90 / 1.5 + 100, 0 / 1.5 + 200)
    assert result["rooms"][0]["class"] == "Kitchen"
    assert [120.0, 220.0] in result["rooms"][0]["polygon"]  # (30, 30) -> (120, 220)


def test_a_multipolygon_room_becomes_one_room_per_piece() -> None:
    pieces = MultiPolygon(
        [Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]), Polygon([(5, 5), (7, 5), (7, 7), (5, 7)])]
    )
    result = from_polygons([], [], [pieces], [{"type": "room", "class": 5}], 1.0, (0, 0))
    assert [r["class"] for r in result["rooms"]] == ["Bed Room", "Bed Room"]


def test_from_components_finds_each_object_and_room() -> None:
    rooms = np.zeros((40, 60), int)
    rooms[5:20, 5:25] = ROOMS.index("Bath")
    rooms[5:20, 30:55] = ROOMS.index("Kitchen")
    icons = np.zeros((40, 60), int)
    icons[25:30, 10:14] = ICONS.index("Toilet")
    icons[25:30, 40:44] = ICONS.index("Toilet")  # a second, separate toilet
    result = from_components(rooms, icons, scale=1.0, offset=(0, 0), min_area_px=4)
    assert sorted(o["class"] for o in result["objects"]) == ["Toilet", "Toilet"]
    assert sorted(r["class"] for r in result["rooms"]) == ["Bath", "Kitchen"]
    # The toilet at rows 25..29, cols 10..13 has the box x 10..14, y 25..30 (by hand).
    boxes = sorted(o["polygon"][0] for o in result["objects"])
    assert boxes[0] == [10.0, 25.0]


def test_from_components_ignores_specks_and_background() -> None:
    rooms = np.zeros((20, 20), int)
    icons = np.zeros((20, 20), int)
    icons[3, 3] = ICONS.index("Sink")  # one pixel: below min_area_px
    result = from_components(rooms, icons, scale=1.0, offset=(0, 0), min_area_px=4)
    assert result == {"rooms": [], "walls": [], "objects": []}


def test_rooms_of_the_same_type_are_split_at_a_door_between_them() -> None:
    bed, wall = ROOMS.index("Bed Room"), ROOMS.index("Wall")
    rooms = np.full((30, 61), bed)
    rooms[:, 30] = wall  # one wall column between two bedrooms...
    rooms[10:20, 30] = bed  # ...with a doorway in it, where the model saw a door
    icons = np.zeros((30, 61), int)
    icons[10:20, 29:32] = ICONS.index("Door")
    result = from_components(rooms, icons, scale=1.0, offset=(0, 0), min_area_px=4)
    assert [r["class"] for r in result["rooms"]] == ["Bed Room", "Bed Room"]


def test_walls_come_from_the_wall_class() -> None:
    rooms = np.zeros((30, 30), int)
    rooms[5:8, 2:28] = ROOMS.index("Wall")  # one 3 x 26 px wall
    result = from_components(rooms, np.zeros((30, 30), int), 1.0, (0, 0), min_area_px=4)
    assert len(result["walls"]) == 1
    xs = [p[0] for p in result["walls"][0]]
    assert (min(xs), max(xs)) == (2.0, 27.0)  # contour runs along pixel columns 2..27
