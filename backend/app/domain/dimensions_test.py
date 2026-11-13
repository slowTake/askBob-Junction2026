import pytest

from app.domain.dimensions import mm_per_px, parse_area_m2, parse_dimension_mm, parse_scale


def test_dimension_with_thousands_space() -> None:
    assert parse_dimension_mm("10 800") == 10800
    assert parse_dimension_mm("11\u00a0280") == 11280


def test_plain_dimension() -> None:
    assert parse_dimension_mm("3600") == 3600
    assert parse_dimension_mm("70") == 70


def test_dimension_rejects_codes_and_tiny_numbers() -> None:
    assert parse_dimension_mm("09") is None  # door tag, not a dimension
    assert parse_dimension_mm("12") is None  # below 50 mm: grid label
    assert parse_dimension_mm("MH") is None


def test_scale() -> None:
    assert parse_scale("1:50") == 50
    assert parse_scale("1 : 100") == 100
    assert parse_scale("2:50") is None


def test_area() -> None:
    assert parse_area_m2("80M2") == 80.0
    assert parse_area_m2("80M²") == 80.0
    assert parse_area_m2("12,5 m2") == 12.5
    assert parse_area_m2("80") is None


def test_mm_per_px() -> None:
    # 150 dpi -> one pixel is 25.4 / 150 = 0.16933 mm on paper; at 1:50 that is 8.4667 mm.
    assert mm_per_px(150, 50) == pytest.approx(8.46667, rel=1e-4)
