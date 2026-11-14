import numpy as np
import pytest

from app.domain.tokens import Word
from app.ingest import ocr
from app.ingest.ocr import pick_langs, upscale_factor


def test_vertical_thousands_stay_one_word(monkeypatch: pytest.MonkeyPatch) -> None:
    # A 3000x4000 page needs no upscale. Tesseract finds nothing upright, and in the
    # 90° pass (4000x3000) reads a vertical "2 400" as two words side by side, as on
    # real pages (#69). They must be merged before unrotating, where they would sit
    # one above the other and no longer look like one number.
    def fake_ocr(image: np.ndarray, langs: str) -> list[Word]:
        if image.shape == (3000, 4000):
            return []
        return [Word((100.0, 200.0, 114.0, 220.0), "2"), Word((126.0, 200.0, 172.0, 220.0), "400")]

    monkeypatch.setattr(ocr, "_ocr", fake_ocr)
    monkeypatch.setattr(ocr, "_available_langs", lambda: frozenset({"eng"}))
    words = ocr.ocr_words(np.full((3000, 4000), 255, np.uint8), "eng")
    # Merged box (100, 200, 172, 220); unrotated with H = 3000:
    # (y0, H - x1, y1, H - x0) = (200, 2828, 220, 2900).
    assert [(w.text, w.bbox) for w in words] == [("2 400", (200.0, 2828.0, 220.0, 2900.0))]


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
