import pytest

from app.domain.scale_fit import consensus_scale, scale_from_dimension


def test_scale_from_dimension() -> None:
    # A 3600 mm dimension whose line is 120 px long: 3600 / 120 = 30 mm per pixel.
    assert scale_from_dimension(3600, 120.0) == 30.0


def test_scale_from_dimension_rejects_degenerate_lines() -> None:
    assert scale_from_dimension(3600, 0.0) is None
    assert scale_from_dimension(3600, -5.0) is None


def test_consensus_keeps_the_agreeing_group_and_drops_the_outlier() -> None:
    # Within 3% of 10.0 (9.7..10.3): 9.9, 10.0, 10.2. 25.0 is a misread label.
    # Median of [9.9, 10.0, 10.2] is 10.0; three labels support it.
    assert consensus_scale([10.0, 10.2, 9.9, 25.0]) == (10.0, 3)


def test_consensus_median_of_an_even_group() -> None:
    # (10.0 + 10.2) / 2 = 10.1
    result = consensus_scale([10.0, 10.2])
    assert result is not None
    assert result[0] == pytest.approx(10.1)
    assert result[1] == 2


def test_consensus_needs_two_agreeing_labels_by_default() -> None:
    assert consensus_scale([]) is None
    assert consensus_scale([10.0]) is None
    assert consensus_scale([10.0, 20.0]) is None  # 20.0 is 100% off, not within 3%


def test_consensus_single_label_when_allowed() -> None:
    assert consensus_scale([10.0], min_support=1) == (10.0, 1)


def test_consensus_ignores_non_positive_values() -> None:
    # Only 10.0 and 10.1 count; their median is 10.05.
    result = consensus_scale([0.0, -1.0, 10.0, 10.1])
    assert result is not None
    assert result[0] == pytest.approx(10.05)
    assert result[1] == 2


def test_consensus_prefers_the_larger_group() -> None:
    # Two groups: {5.0, 5.05} and {20.0, 20.1, 19.9}. The larger one wins; median 20.0.
    assert consensus_scale([5.0, 20.0, 5.05, 20.1, 19.9]) == (20.0, 3)
