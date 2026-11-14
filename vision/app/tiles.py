"""Tiling a big page for the network, and mapping results back to the original image."""

from collections.abc import Iterable, Sequence

import numpy as np


def tile_starts(length: int, tile: int, overlap: int) -> list[int]:
    """Start offsets of tiles covering `length`; the last tile ends flush with the edge."""
    if length <= tile:
        return [0]
    starts = list(range(0, length - tile, tile - overlap))
    return [*starts, length - tile]


def edge_weights(n: int, overlap: int) -> np.ndarray:
    """Per-pixel blend weight along one tile side: fades to the edges, 1 in the middle.

    Predictions near a tile edge see less context, so overlapping tiles trust each
    other's middles. Never zero, so a pixel covered by one tile keeps its value.
    """
    i = np.arange(n)
    return np.minimum(np.minimum(i + 1, n - i) / overlap, 1.0)


def to_original(
    points: Iterable[Sequence[float]], scale: float, offset: tuple[float, float]
) -> list[list[float]]:
    """Scaled-crop pixels -> original-image pixels."""
    a = np.asarray(list(points), dtype=float).reshape(-1, 2) / scale + np.asarray(offset)
    return [[round(float(x), 1), round(float(y), 1)] for x, y in a]


def keep_windows(starts: list[int], tile: int, length: int) -> list[tuple[int, int]]:
    """For each tile, the part (in its own coordinates) it alone owns.

    Neighbouring tiles split their overlap in the middle, so every pixel comes from
    exactly one tile, and from that tile's inner part rather than its edge.
    """
    ends = [min(s + tile, length) for s in starts]
    cuts = [0] + [(ends[i] + starts[i + 1]) // 2 for i in range(len(starts) - 1)] + [length]
    return [(cuts[i] - s, cuts[i + 1] - s) for i, s in enumerate(starts)]
