from app.ingest.ocr import pick_langs, upscale_factor


def test_pick_installed_languages_only() -> None:
    assert pick_langs("fin+swe+eng", {"eng", "fin", "osd"}) == "fin+eng"


def test_fall_back_to_english() -> None:
    assert pick_langs("fin+swe", {"osd"}) == "eng"


def test_upscale_small_images() -> None:
    # 763 px screenshot: ceil(3000 / 763) = 4 (3.93 rounded up), within the cap of 4.
    assert upscale_factor(763) == 4
    # 1200 px: ceil(3000 / 1200) = 3.
    assert upscale_factor(1200) == 3


def test_no_upscale_for_large_or_empty_images() -> None:
    assert upscale_factor(3000) == 1
    assert upscale_factor(9000) == 1
    assert upscale_factor(0) == 1


def test_upscale_is_capped() -> None:
    assert upscale_factor(200) == 4  # ceil(3000 / 200) = 15, capped at 4
