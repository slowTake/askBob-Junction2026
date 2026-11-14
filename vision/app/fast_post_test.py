"""The fast helpers must give exactly what CubiCasa's originals give.

`_reference_*` restate the originals' behaviour plainly (list membership, a copy,
a per-pixel argmax); seeded random cases compare them with the fast versions.
"""

import random
from itertools import combinations
from types import ModuleType
from typing import Any

import numpy as np

from app.fast_post import PixelClasses, drop_long_walls, get_polygon_class, install


def _reference_drop(walls: list[Any], points: Any, same_corner: Any, length: Any) -> list[Any]:
    bad: list[Any] = []
    remaining: list[Any] = []
    for w1, w2 in combinations(walls, 2):
        if w1 not in bad and w2 not in bad and same_corner(w1, w2, points):
            if length(w1, points) <= length(w2, points):
                good = w1
                bad.append(w2)
            else:
                good = w2
                bad.append(w1)
            if good not in remaining:
                remaining.append(good)
        else:
            if w1 not in remaining and w1 not in bad:
                remaining.append(w1)
            if w2 not in remaining and w2 not in bad:
                remaining.append(w2)
    return [w for w in remaining if w not in bad]


def _geometry(points: list[tuple[int, int]]) -> tuple[Any, Any]:
    def dim(wall: Any) -> int:
        (x1, y1), (x2, y2) = points[wall[0]], points[wall[1]]
        return 0 if abs(x2 - x1) >= abs(y2 - y1) else 1

    def same_corner(w1: Any, w2: Any, _: Any) -> bool:
        return dim(w1) == dim(w2) and (w1[0] == w2[0] or w1[1] == w2[1])

    def length(wall: Any, _: Any) -> float:
        (x1, y1), (x2, y2) = points[wall[0]], points[wall[1]]
        return float(abs(x2 - x1) + abs(y2 - y1))

    return same_corner, length


def test_drop_long_walls_matches_the_original_on_random_plans() -> None:
    rng = random.Random(7)
    for _ in range(300):
        points = [(rng.randrange(20), rng.randrange(20)) for _ in range(rng.randrange(2, 9))]
        walls = [
            (rng.randrange(len(points)), rng.randrange(len(points)))
            for _ in range(rng.randrange(0, 25))
        ]  # duplicates included, as equal walls compare equal in the original
        same_corner, length = _geometry(points)
        assert drop_long_walls(walls, points, same_corner, length) == _reference_drop(
            walls, points, same_corner, length
        )


def test_drop_long_walls_keeps_the_shorter_of_two_from_one_corner() -> None:
    # Points: 0=(0,0), 1=(5,0), 2=(9,0). Walls 0-1 (length 5) and 0-2 (length 9) are
    # both horizontal from corner 0, so the longer 0-2 goes (by hand).
    points = [(0, 0), (5, 0), (9, 0)]
    same_corner, length = _geometry(points)
    assert drop_long_walls([(0, 1), (0, 2)], points, same_corner, length) == [(0, 1)]


def _reference_class(polygon: Any, seg: Any) -> Any:
    from skimage import draw

    seg_copy = np.copy(seg)
    jj, ii = draw.polygon(polygon[:, 1], polygon[:, 0], shape=seg_copy.shape)
    values, counts = np.unique(seg_copy[jj, ii], return_counts=True)
    return values[np.argmax(counts)] if len(counts) else None


def test_polygon_class_matches_the_original() -> None:
    rng = np.random.default_rng(3)
    seg = rng.integers(0, 5, size=(40, 60))
    for _ in range(50):
        x0, y0 = rng.integers(0, 50), rng.integers(0, 30)
        x1, y1 = x0 + rng.integers(0, 15), y0 + rng.integers(0, 15)
        polygon = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
        assert get_polygon_class(polygon, seg) == _reference_class(polygon, seg)
    assert seg.flags.writeable  # read only, never changed


def test_a_polygon_outside_the_map_has_no_class() -> None:
    seg = np.zeros((10, 10), int)
    assert get_polygon_class(np.array([[50, 50], [60, 50], [60, 60], [50, 60]]), seg) is None


def test_pixel_class_matches_a_per_pixel_argmax_including_ties() -> None:
    rng = np.random.default_rng(5)
    seg = rng.integers(0, 3, size=(6, 20, 30)).astype(float)  # many ties: first index wins
    pixel = PixelClasses()
    for j in range(20):
        for i in range(30):
            assert pixel(i, j, seg) == np.argmax(seg[:, j, i])


def test_pixel_class_follows_a_new_segmentation() -> None:
    pixel = PixelClasses()
    first = np.zeros((2, 3, 3))
    first[1] = 1.0
    second = np.zeros((2, 3, 3))
    second[0] = 1.0
    assert pixel(0, 0, first) == 1
    assert pixel(0, 0, second) == 0


def test_install_rebinds_the_three_helpers_and_keeps_the_rest() -> None:
    module = ModuleType("post_prosessing")
    for name in (
        "drop_long_walls",
        "get_polygon_class",
        "get_pxl_class",
        "walls_same_corner",
        "get_wall_length",
    ):
        setattr(module, name, name)
    install(module)
    assert module.get_polygon_class is get_polygon_class
    assert isinstance(module.get_pxl_class, PixelClasses)
    assert callable(module.drop_long_walls)
    assert module.walls_same_corner == "walls_same_corner"
