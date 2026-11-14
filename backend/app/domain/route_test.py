from itertools import pairwise

import numpy as np
import pytest

from app.domain.route import Obstacles, find_route, route_length_px, walkable

# A 100 x 60 px page. A vertical wall at x 48..52 splits it into two rooms.
WALL = (48.0, 0.0, 52.0, 60.0)


def _grid(*, door: bool) -> np.ndarray:
    doors = [(46.0, 25.0, 54.0, 35.0)] if door else []  # an opening at y 25..35
    return walkable((100, 60), Obstacles(walls=[WALL], wall_polygons=[], doors=doors), cell=2)


def test_a_wall_without_a_door_blocks_the_way() -> None:
    assert find_route(_grid(door=False), (10, 30), (90, 30), cell=2) is None


def test_the_route_goes_through_the_door() -> None:
    route = find_route(_grid(door=True), (10, 10), (90, 10), cell=2)
    assert route is not None
    assert route[0] == pytest.approx((10, 10), abs=2) and route[-1] == pytest.approx(
        (90, 10), abs=2
    )
    # Every point of the route inside the wall's band x 48..52 is in the door's span y 25..35.
    inside = [
        (x0 + (x1 - x0) * t / 100, y0 + (y1 - y0) * t / 100)
        for (x0, y0), (x1, y1) in pairwise(route)
        for t in range(101)
    ]
    crossing = [y for x, y in inside if 48 <= x <= 52]
    assert crossing and all(24 <= y <= 36 for y in crossing)


def test_the_route_is_simplified_to_few_corners() -> None:
    route = find_route(_grid(door=True), (10, 30), (90, 30), cell=2)
    assert route is not None and len(route) <= 4  # a straight run through the door


def test_open_space_gives_a_straight_route_of_the_straight_length() -> None:
    free = walkable((100, 60), Obstacles(walls=[], wall_polygons=[], doors=[]), cell=2)
    route = find_route(free, (10, 30), (90, 30), cell=2)
    assert route is not None and len(route) == 2
    assert route_length_px(route) == pytest.approx(80, abs=2)  # 90 - 10, by hand


def test_an_end_inside_a_wall_moves_to_the_nearest_free_spot() -> None:
    route = find_route(_grid(door=True), (50, 5), (90, 10), cell=2)  # starts in the wall
    assert route is not None


def test_wall_polygons_block_like_boxes() -> None:
    poly = [(48.0, 0.0), (52.0, 0.0), (52.0, 60.0), (48.0, 60.0)]
    free = walkable((100, 60), Obstacles(walls=[], wall_polygons=[poly], doors=[]), cell=2)
    assert find_route(free, (10, 30), (90, 30), cell=2) is None


def test_route_length_adds_the_segments() -> None:
    assert route_length_px([(0, 0), (3, 4), (3, 10)]) == pytest.approx(11)  # 5 + 6
