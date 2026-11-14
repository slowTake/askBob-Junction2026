from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from app.config import Settings
from app.ingest import image_reader
from app.ingest.errors import ReaderError


def test_transparent_png_is_composited_on_white() -> None:
    image = Image.new("RGBA", (3, 1), (0, 0, 0, 0))
    image.putpixel((1, 0), (0, 0, 0, 255))
    image.putpixel((2, 0), (0, 0, 0, 128))
    result = image_reader._on_white(image)
    assert result.mode == "RGB"
    assert result.getpixel((0, 0)) == (255, 255, 255)
    assert result.getpixel((1, 0)) == (0, 0, 0)
    assert result.getpixel((2, 0)) == (127, 127, 127)


def test_palette_transparency_and_opaque_colours() -> None:
    image = Image.new("P", (2, 1))
    image.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
    image.info["transparency"] = 0
    image.putpixel((1, 0), 1)
    result = image_reader._on_white(image)
    assert result.getpixel((0, 0)) == (255, 255, 255)
    assert result.getpixel((1, 0)) == (255, 0, 0)
    rgb = Image.new("RGB", (1, 1), "blue")
    assert image_reader._on_white(rgb).getpixel((0, 0)) == (0, 0, 255)


def test_png_reports_progress_before_slow_stages_and_survives_vision_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "drawing.png"
    Image.new("RGBA", (20, 10), (0, 0, 0, 0)).save(path)
    events: list[tuple[str, float]] = []

    def ocr(*args: Any) -> list[Any]:
        assert events[-1] == ("ocr", 0.0)
        return []

    def vision(*args: Any) -> tuple[None, str]:
        assert events[-1] == ("vision", 0.3)
        return None, "failed"

    def annotate(*args: Any, **kwargs: Any) -> tuple[list[Any], None, dict[str, Any]]:
        assert events[-1] == ("annotating", 0.8)
        assert kwargs["vision"] is None
        return [], None, {}

    monkeypatch.setattr(image_reader, "page_words", ocr)
    monkeypatch.setattr(image_reader, "analyse_page", vision)
    monkeypatch.setattr(image_reader, "annotate_page", annotate)
    result = image_reader.read_image(
        path, Settings.model_construct(), lambda s, f: events.append((s, f))
    )
    assert len(result.pages) == 1
    assert result.pages[0].meta["vision"] == "failed"
    assert result.pages[0].image_png.startswith(b"\x89PNG")
    assert events[-1] == ("annotating", 1.0)


def test_invalid_image_has_a_safe_error_code(tmp_path: Path) -> None:
    path = tmp_path / "broken.png"
    path.write_bytes(b"invalid")
    with pytest.raises(ReaderError) as raised:
        image_reader.read_image(path, Settings.model_construct(), lambda *_: None)
    assert raised.value.code == "unreadable_file"
