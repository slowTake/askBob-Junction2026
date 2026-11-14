import pytest

from app.domain.tokens import Word
from app.ingest import ocr as ocr_module
from app.ingest.ocr import clean_text, dedupe_words, pick_langs, tile_starts, upscale_factor


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


# --- RapidOCR (D-024) -----------------------------------------------------------


def test_clean_text_drops_non_latin_noise_and_edge_punctuation() -> None:
    # RapidOCR's default model reads CJK; on these drawings that is always noise.
    assert clean_text(".1.12]") == "1.12"
    assert clean_text("通") == ""
    assert clean_text("App. A]") == "App. A"
    assert clean_text("Küche") == "Küche"
    assert clean_text("15.61 m²") == "15.61 m²"


def test_tiles_cover_the_page_and_end_flush() -> None:
    # step 1600 - 200 = 1400; starts below 3000 - 1600 = 1400 are 0, then 1400 (by hand)
    assert tile_starts(3000, tile=1600, overlap=200) == [0, 1400]
    assert tile_starts(1000, tile=1600, overlap=200) == [0]


def test_dedupe_keeps_the_surer_reading_of_a_word_seen_twice() -> None:
    a = Word((0.0, 0.0, 40.0, 10.0), "1.04", 0.9)
    b = Word((1.0, 0.0, 41.0, 10.0), "1.O4", 0.6)  # same word, other tile, worse read
    c = Word((100.0, 0.0, 140.0, 10.0), "Bad", 0.8)
    assert dedupe_words([b, a, c]) == [a, c]


def test_falls_back_to_tesseract_when_rapidocr_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(gray: object) -> list[Word]:
        raise RuntimeError("onnx session failed")

    monkeypatch.setattr(ocr_module, "_rapid_words", broken)
    monkeypatch.setattr(
        ocr_module, "_tesseract_words", lambda gray, langs: [Word((0, 0, 1, 1), "ok")]
    )
    assert [w.text for w in ocr_module.ocr_words(None, "eng", engine="rapid")] == ["ok"]  # type: ignore[arg-type]
