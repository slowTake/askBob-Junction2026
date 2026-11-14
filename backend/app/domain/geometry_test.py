import pytest

from app.domain.geometry import (
    bbox_iou,
    bbox_to_plan_polygon,
    bbox_union,
    distance,
    footprint_mm,
    measure_boxes,
    polygon_area,
    px_to_plan_mm,
    unrotate_bbox_cw90,
)


def test_union() -> None:
    assert bbox_union((0, 0, 2, 2), (1, 1, 3, 4)) == (0, 0, 3, 4)


def test_iou() -> None:
    # Two 2x2 squares overlapping in a 1x2 strip: inter 2, union 4 + 4 - 2 = 6.
    assert bbox_iou((0, 0, 2, 2), (1, 0, 3, 2)) == pytest.approx(2 / 6)
    assert bbox_iou((0, 0, 1, 1), (5, 5, 6, 6)) == 0.0


def test_unrotate_cw90() -> None:
    # Original image 100 wide, 40 high. Pixel (10, 5) rotates clockwise to (40 - 5, 10) = (35, 10).
    # A box around it in the rotated image, (34, 9, 36, 11), maps back to (9, 4, 11, 6).
    assert unrotate_bbox_cw90((34, 9, 36, 11), original_height=40) == (9, 4, 11, 6)


def test_polygon_area_rectangle_both_windings() -> None:
    # Room 3030 x 3415 mm -> 10 347 450 mm² (10.35 m²), hand calculation.
    ccw = [(0.0, 0.0), (3030.0, 0.0), (3030.0, 3415.0), (0.0, 3415.0)]
    assert polygon_area(ccw) == pytest.approx(10_347_450)
    assert polygon_area(list(reversed(ccw))) == pytest.approx(10_347_450)


def test_polygon_area_degenerate() -> None:
    assert polygon_area([(0, 0), (1, 1)]) == 0.0


def test_distance() -> None:
    assert distance((0, 0), (3, 4)) == 5.0  # 3-4-5 triangle


def test_px_to_plan_flips_y() -> None:
    # Page 1000 px high, 10 mm per px: pixel (100, 900) is 100 px above the bottom edge.
    assert px_to_plan_mm((100, 900), 10, 1000) == (1000, 1000)


def test_footprint_mm_flips_and_scales_each_point() -> None:
    # Page 100 px high, 5 mm/px: (10, 100) -> (50, 0) and (10, 80) -> (50, 100).
    assert footprint_mm([(10, 100), (10, 80)], 5, 100) == [(50, 0), (50, 100)]


def test_bbox_to_plan_polygon() -> None:
    poly = bbox_to_plan_polygon((0, 0, 10, 20), mm_per_px=2, page_height_px=20)
    assert poly == [(0, 0), (20, 0), (20, 40), (0, 40)]
    assert polygon_area(poly) == 800  # 20 mm x 40 mm


def test_measure_boxes_side_by_side() -> None:
    # Two 10x10 px boxes, 20 px apart edge to edge, centres 30 px apart; 5 mm per px.
    m = measure_boxes((0, 0, 10, 10), (30, 0, 40, 10), mm_per_px=5)
    assert m.centre_mm == 150  # 30 px x 5 mm
    assert m.gap_mm == 100  # 20 px x 5 mm
    assert (m.start, m.end) == ((5, 5), (35, 5))  # centre to centre


def test_measure_boxes_diagonal_and_overlapping() -> None:
    # Gap: 3 px across and 4 px down between the nearest corners -> 5 px (3-4-5).
    assert measure_boxes((0, 0, 10, 10), (13, 14, 20, 20), mm_per_px=1).gap_mm == 5
    assert measure_boxes((0, 0, 10, 10), (5, 5, 20, 20), mm_per_px=1).gap_mm == 0
