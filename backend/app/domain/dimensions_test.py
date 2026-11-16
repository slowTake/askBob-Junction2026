import pytest

from app.domain.dimensions import (
    mm_per_px,
    parse_area_m2,
    parse_dimension_mm,
    parse_height_mm,
    parse_scale,
)


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


def test_scale_inside_a_title_line() -> None:
    # Swiss dataset title lines, one per language.
    assert parse_scale("Massstab 1:200 (A3) · Masse in Metern") == 200
    assert parse_scale("Échelle 1:100 (A3) · Cotes en mètres") == 100
    assert parse_scale("Scala 1:50") == 50
    assert parse_scale("ratio 21:9") is None  # not a 1:n scale


def test_decimal_comma_metres_with_three_decimals() -> None:
    # colorful-34 prints dimensions in metres to the millimetre: "5,341" m = 5341 mm.
    assert parse_dimension_mm("5,341") == 5341
    assert parse_dimension_mm("10,198") == 10198
    assert parse_dimension_mm("0,450") == 450  # 0.450 m
    assert parse_dimension_mm("0,045") is None  # 45 mm: under the 50 mm floor


def test_decimal_comma_with_fewer_decimals_is_ambiguous() -> None:
    # "2,40" could be metres (2400 mm), an area without a unit or a height in metres;
    # "0,5" likewise. Three decimals are millimetres whether read as metres or as a
    # thousands comma, so only those are dimensions.
    assert parse_dimension_mm("2,40") is None
    assert parse_dimension_mm("0,5") is None
    assert parse_dimension_mm("5,3410") is None
    assert parse_dimension_mm("1234,567") is None  # 1.2 km: not a building dimension


def test_area_with_decimal_comma_is_not_a_dimension() -> None:
    assert parse_dimension_mm("12,5 m2") is None
    assert parse_area_m2("12,5 m2") == 12.5


def test_height_labels() -> None:
    # "h1600": a ceiling height of 1600 mm, h followed by 3-4 digits (colorful-34).
    assert parse_height_mm("h1600") == 1600
    assert parse_height_mm("h745") == 745
    assert parse_height_mm("H2388") == 2388
    assert parse_height_mm("h746-") == 746  # a leader stroke read as a dash
    assert parse_height_mm("-h1870") == 1870


def test_height_label_rejects_other_text() -> None:
    assert parse_height_mm("h16go") is None  # misread digits
    assert parse_height_mm("h12") is None  # too few digits
    assert parse_height_mm("h12345") is None
    assert parse_height_mm("h0600") is None  # leading zero
    assert parse_height_mm("M1986") is None  # another letter: not guessed to be an h
    assert parse_height_mm("1600") is None
