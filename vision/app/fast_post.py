"""Faster drop-in versions of three CubiCasa post-processing helpers, same results.

Profiled on a 1902 x 810 px Swiss plan on Verda: the network took 0.8 s, CubiCasa's
`get_polygons` 24.7 s, almost all of it in three helpers of
`floortrans/post_prosessing.py`. We don't edit their code (D-022: fetched at build
time, CC BY-NC); `install` rebinds the helpers on their module, whose own functions
look them up there at call time.

- `drop_long_walls` kept its bad and remaining walls in lists, so every `in` check
  scanned a list inside an all-pairs loop. Sets for membership, the list for order.
- `get_polygon_class` copied the whole room map on every call (2 666 calls) and only
  read it.
- `get_pxl_class` ran `argmax` over one pixel's classes 945 000 times. The argmax of
  the whole map is computed once per segmentation and indexed instead; `argmax`
  breaks ties by the first index either way.
"""

from collections.abc import Callable, Hashable, Sequence
from itertools import combinations
from types import ModuleType
from typing import Any

import numpy as np

Wall = Any  # CubiCasa's walls are pairs of point indices
SameCorner = Callable[[Wall, Wall, Any], bool]
Length = Callable[[Wall, Any], float]


def _key(wall: Wall) -> Hashable:
    return tuple(wall)


def drop_long_walls(
    walls: Sequence[Wall], wall_points: Any, same_corner: SameCorner, length: Length
) -> list[Wall]:
    """Of two same-direction walls sharing a corner, keep the shorter (as CubiCasa)."""
    bad: set[Hashable] = set()
    kept: set[Hashable] = set()
    remaining: list[Wall] = []

    def keep(wall: Wall, key: Hashable) -> None:
        if key not in kept:
            kept.add(key)
            remaining.append(wall)

    for wall1, wall2 in combinations(walls, 2):
        k1, k2 = _key(wall1), _key(wall2)
        if k1 not in bad and k2 not in bad and same_corner(wall1, wall2, wall_points):
            if length(wall1, wall_points) <= length(wall2, wall_points):
                bad.add(k2)
                keep(wall1, k1)
            else:
                bad.add(k1)
                keep(wall2, k2)
        else:
            if k1 not in bad:
                keep(wall1, k1)
            if k2 not in bad:
                keep(wall2, k2)
    return [wall for wall in remaining if _key(wall) not in bad]


def get_polygon_class(polygon: Any, segmentation: Any, remove_layers: Any = None) -> Any:
    """The most common class inside the polygon; None if it covers no pixel."""
    from skimage import draw

    jj, ii = draw.polygon(polygon[:, 1], polygon[:, 0], shape=segmentation.shape)
    values, counts = np.unique(segmentation[jj, ii], return_counts=True)
    return values[np.argmax(counts)] if len(counts) else None


class PixelClasses:
    """`get_pxl_class` with the argmax map of the last segmentation cached."""

    def __init__(self) -> None:
        self._source: Any = None
        self._labels: Any = None

    def __call__(self, i: int, j: int, segmentation: Any) -> Any:
        if segmentation is not self._source:
            self._labels = np.argmax(segmentation, axis=0)
            self._source = segmentation
        return self._labels[j, i]


def install(post_processing: ModuleType) -> None:
    pp = post_processing
    same_corner, length = pp.walls_same_corner, pp.get_wall_length
    setattr(  # noqa: B010 - rebinding a module attribute, which is the point
        pp,
        "drop_long_walls",
        lambda walls, points: drop_long_walls(walls, points, same_corner, length),
    )
    setattr(pp, "get_polygon_class", get_polygon_class)  # noqa: B010
    setattr(pp, "get_pxl_class", PixelClasses())  # noqa: B010
