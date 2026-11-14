"""Dimensions printed under room names are not room numbers (PR #65 review)."""

from pathlib import Path

import pymupdf

from app.config import Settings
from app.ingest.pdf_reader import read_pdf


def test_nordic_rooms_with_dimensions_under_their_names_all_stay_rooms(tmp_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    rooms = [("MH", 100, 100), ("OH", 350, 100), ("KH", 100, 330), ("K", 350, 330)]
    for name, x, y in rooms:
        page.draw_rect(pymupdf.Rect(x, y, x + 220, y + 200), width=3)
        page.insert_text((x + 100, y + 90), name, fontsize=10)
    for (_, x, y), dim in zip(rooms[:3], ["3.20", "4.10", "2.75"], strict=True):
        page.insert_text((x + 95, y + 110), dim, fontsize=10)  # a dimension under the name
    page.insert_text((700, 570), "1:50", fontsize=10)
    path = tmp_path / "nordic.pdf"
    doc.save(path)
    settings = Settings(database_url="x", valkey_url="x", ocr_langs="eng")
    res = read_pdf(path, settings, lambda stage, fraction: None)
    found = {e.text: e for e in res.pages[0].elements if e.text in {"MH", "OH", "KH", "K"}}
    assert {t: e.kind for t, e in found.items()} == {
        "MH": "room",
        "OH": "room",
        "KH": "room",
        "K": "room",
    }
    assert all("number" not in e.properties for e in found.values())
