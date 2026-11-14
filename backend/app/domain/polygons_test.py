from app.domain.polygons import (
    clean_polygon,
    cluster_boxes,
    cluster_by_endpoints,
    path_polygon,
    point_in_polygon,
    polygon_bbox,
)

SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
# An L shape: the 10x10 square minus its top-right 5x5 quarter.
L_SHAPE = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (5.0, 5.0), (5.0, 10.0), (0.0, 10.0)]


def test_point_in_square() -> None:
    assert point_in_polygon((5, 5), SQUARE)
    assert not point_in_polygon((15, 5), SQUARE)


def test_point_in_concave_polygon() -> None:
    assert point_in_polygon((2, 8), L_SHAPE)  # in the left arm
    assert not point_in_polygon((8, 8), L_SHAPE)  # in the cut-out quarter


def test_polygon_bbox() -> None:
    assert polygon_bbox(L_SHAPE) == (0, 0, 10, 10)


def test_cluster_touching_and_transitive() -> None:
    boxes = [(0, 0, 1, 1), (1, 0, 2, 1), (2.05, 0, 3, 1), (10, 10, 11, 11)]
    # 0 touches 1; 1 is 0.05 from 2 (within gap 0.1); 3 is far away.
    assert cluster_boxes(boxes, gap=0.1) == [[0, 1, 2], [3]]


def test_cluster_without_gap_keeps_separate_boxes_apart() -> None:
    assert cluster_boxes([(0, 0, 1, 1), (1.5, 0, 2, 1)], gap=0.0) == [[0], [1]]


def test_negative_gap_requires_overlap() -> None:
    # Two windows side by side share an edge at x=1: touching, not overlapping.
    side_by_side = [(0, 0, 1, 1), (1, 0, 2, 1)]
    assert cluster_boxes(side_by_side, gap=-0.01) == [[0], [1]]
    # Frame and inner line of one window overlap: same cluster.
    assert cluster_boxes([(0, 0, 1, 1), (0.1, 0.4, 0.9, 0.6)], gap=-0.01) == [[0, 1]]


def test_double_door_arcs_share_an_endpoint() -> None:
    # Two leaves of a double door meet at (1, 0); a single door elsewhere touches
    # neither endpoint, even though its arc passes close by.
    left = ((0.0, 1.0), (1.0, 0.0))
    right = ((1.0, 0.0), (2.0, 1.0))
    single = ((5.0, 0.0), (6.0, 1.0))
    assert cluster_by_endpoints([left, right, single], tolerance=0.01) == [[0, 1], [2]]


def test_identical_arcs_stay_separate() -> None:
    arc = ((0.0, 1.0), (1.0, 0.0))
    assert cluster_by_endpoints([arc, arc], tolerance=0.01) == [[0], [1]]


def test_path_ops_to_polygon() -> None:
    # A closed outline drawn as three lines plus a curve back to the start: vertices
    # are each segment's start point; the final end point closes it and is dropped.
    ops = [
        ("l", [(0.0, 0.0), (10.0, 0.0)]),
        ("l", [(10.0, 0.0), (10.0, 5.0)]),
        ("l", [(10.0, 5.0), (0.0, 5.0)]),
        ("c", [(0.0, 5.0), (-1.0, 4.0), (-1.0, 1.0), (0.0, 0.0)]),
    ]
    assert path_polygon(ops) == [(0, 0), (10, 0), (10, 5), (0, 5)]


def test_rect_op_becomes_four_corners() -> None:
    assert path_polygon([("re", [(1.0, 2.0), (4.0, 6.0)])]) == [(1, 2), (4, 2), (4, 6), (1, 6)]


def test_clean_polygon_drops_repeats_and_closing_point() -> None:
    raw = [(0.0, 0.0), (0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (10.0, 5.0005), (0.0, 5.0), (0.0, 0.0)]
    assert clean_polygon(raw, tolerance=0.01) == [(0, 0), (10, 0), (10, 5), (0, 5)]


def test_clean_polygon_rejects_degenerate_shapes() -> None:
    assert clean_polygon([(0.0, 0.0), (1.0, 0.0), (1.0, 0.0)], tolerance=0.01) is None
    assert clean_polygon([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)], tolerance=0.01) is None  # no area
