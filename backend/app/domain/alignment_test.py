import math

import pytest

from app.domain.alignment import align_labels, label_anchor

POINTS = [(0.0, 0.0), (100.0, 0.0), (0.0, 100.0), (100.0, 100.0)]


def test_scale_rotation_and_translation() -> None:
    pairs = [(p, (10 - 2 * p[1], 20 + 2 * p[0])) for p in POINTS]
    fit = align_labels(pairs)
    assert fit is not None
    assert fit.apply((25, 10)) == pytest.approx((-10, 70))
    assert fit.scale == pytest.approx(2)
    assert fit.rms_px == pytest.approx(0)
    assert fit.support == 4


def test_one_bad_ocr_anchor_does_not_move_the_rooms() -> None:
    pairs = [(p, (p[0] + 10, p[1] + 20)) for p in POINTS]
    pairs.append(((50, 50), (5000, 8000)))
    fit = align_labels(pairs)
    assert fit is not None and fit.support == 4
    assert fit.apply((25, 10)) == pytest.approx((35, 30))


def test_bad_or_insufficient_alignment_is_rejected() -> None:
    assert align_labels([]) is None
    assert align_labels([((0, 0), (0, 0))] * 3) is None
    assert align_labels([((0, 0), (0, 0)), ((1, 0), (1, 0))]) is None
    assert align_labels([(p, p) for p in POINTS], tolerance_px=0) is None
    assert align_labels([((math.nan, 0), (1, 2))] * 3) is None
    assert (
        align_labels(
            [(POINTS[i], p) for i, p in enumerate([(0, 0), (100, 0), (0, 300), (999, 999)])], 0.1
        )
        is None
    )


def test_dxf_text_alignment_matches_the_correct_point_in_the_ocr_box() -> None:
    box = (10.0, 20.0, 50.0, 40.0)
    assert label_anchor(box, 1, 2) == (30, 30)  # middle-centre
    assert label_anchor(box, 0, 0) == (10, 40)  # left baseline
    assert label_anchor(box, 2, 3) == (50, 20)  # top right
    assert label_anchor(box, 4, 0) == (30, 30)  # DXF middle alignment
