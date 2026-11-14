import pytest

from app.ingest.ocr import pick_langs, upscale_factor


def test_pick_installed_languages_only() -> None:
    assert pick_langs("fin+swe+eng", {"eng", "fin", "osd"}) == "fin+eng"


def test_fall_back_to_english() -> None:
    assert pick_langs("fin+swe", {"osd"}) == "eng"


def test_upscale_to_the_target_not_beyond() -> None:
    # Exact factor, not rounded up: 2480 px -> 3500 px is x1.41 (a whole-number x2
    # would read 4960 px, twice the pixels for nothing).
    assert upscale_factor(2480) == pytest.approx(3500 / 2480)
    assert upscale_factor(1400) == pytest.approx(2.5)  # 3500 / 1400


def test_no_upscale_for_large_or_empty_images() -> None:
    assert upscale_factor(3500) == 1
    assert upscale_factor(9000) == 1
    assert upscale_factor(0) == 1


def test_upscale_is_capped() -> None:
    assert upscale_factor(200) == 4  # 3500 / 200 = 17.5, capped at 4
