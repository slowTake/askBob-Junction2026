from eval.swiss_rooms import FloorScore, score_floor


def test_found_rooms_and_areas_within_five_percent() -> None:
    truth = {"1.01": 10.0, "1.02": 20.0, "1.03": 5.0, "1.04": 8.0}
    # 1.01: 10.4 is 4% off -> ok; 1.02: 22 is 10% off -> found, wrong area;
    # 1.03: named but no outline -> not found; 1.04: not read at all.
    traced = {"1.01": 10.4, "1.02": 22.0, "1.03": None}
    assert score_floor(truth, traced) == FloorScore(rooms=4, named=3, outlined=2, area_ok=1)


def test_rooms_missing_from_the_dxf_are_ignored() -> None:
    # A number OCR invented (or a room the DXF doesn't have) is not scored.
    assert score_floor({"1.01": 10.0}, {"1.01": 10.0, "9.99": 3.0}) == FloorScore(1, 1, 1, 1)


def test_scores_add_up() -> None:
    assert FloorScore(4, 3, 2, 1) + FloorScore(1, 1, 1, 1) == FloorScore(5, 4, 3, 2)
