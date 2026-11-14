"""Rendered pages draw every letter of the drawing's text, not boxes (Swiss, Nordic plans)."""

from PIL import Image, ImageDraw

from app.ingest import render


def _glyph(text: str) -> bytes:
    image = Image.new("L", (120, 90))
    ImageDraw.Draw(image).text((10, 70), text, font=render.font(48), fill=255, anchor="ls")
    return image.tobytes()


def test_a_unicode_font_is_installed() -> None:
    # Docker and CI install fonts-dejavu-core; on Arch install ttf-dejavu or noto-fonts.
    assert render.font_path() is not None


def test_accented_letters_are_drawn_not_as_missing_glyph_boxes() -> None:
    # U+10FFFD is a private-use code point no font draws: it shows the "missing" box.
    missing = _glyph("\U0010fffd")
    for letter in ["é", "è", "É", "â", "ä", "ö", "å", "ç", "ß", "ł", "č"]:
        assert _glyph(letter) != missing, letter


def test_room_labels_keep_their_accents_on_the_page() -> None:
    # "Séjour" must differ from "S?jour" drawn with the box: the é is a real glyph.
    assert _glyph("Sé") != _glyph("S\U0010fffd")
