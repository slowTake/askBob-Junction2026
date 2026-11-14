import numpy as np

from app.tiles import edge_weights, tile_starts, to_original


def test_one_tile_when_the_side_fits() -> None:
    assert tile_starts(1000, tile=1024, overlap=128) == [0]
    assert tile_starts(1024, tile=1024, overlap=128) == [0]


def test_tiles_overlap_and_end_flush_with_the_edge() -> None:
    # step = 1024 - 128 = 896; starts below 2000 - 1024 = 976 are 0 and 896,
    # then a last tile flush with the edge at 976 (by hand).
    assert tile_starts(2000, tile=1024, overlap=128) == [0, 896, 976]


def test_tiles_cover_every_pixel() -> None:
    length, tile = 3333, 1024
    covered = np.zeros(length, bool)
    for start in tile_starts(length, tile=tile, overlap=128):
        covered[start : start + tile] = True
    assert covered.all()


def test_edge_weights_fade_over_the_overlap() -> None:
    # min(i + 1, n - i) / overlap, capped at 1: n=4, overlap=2 -> 1/2, 2/2, 2/2, 1/2 (by hand).
    assert edge_weights(4, overlap=2).tolist() == [0.5, 1.0, 1.0, 0.5]


def test_edge_weights_never_reach_zero() -> None:
    assert edge_weights(1, overlap=128).min() > 0


def test_to_original_undoes_scale_then_adds_crop_offset() -> None:
    # (30 / 1.5 + 100, 60 / 1.5 + 200) = (120, 240), by hand.
    assert to_original([[30, 60]], scale=1.5, offset=(100, 200)) == [[120.0, 240.0]]
