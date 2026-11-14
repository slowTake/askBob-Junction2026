from dataclasses import replace

import pytest

from app.ingest.fusion import fuse_rooms
from app.ingest.types import ExtractedDocument, ExtractedElement, ExtractedPage


def _drawings() -> tuple[ExtractedDocument, ExtractedDocument]:
    rooms, labels = [], []
    for i, (x, y) in enumerate([(10, 10), (110, 10), (10, 110), (110, 110)], 1):
        polygon = [[x - 5, y - 5], [x + 5, y - 5], [x + 5, y + 5], [x - 5, y + 5]]
        rooms.append(
            ExtractedElement(
                "room",
                "dxf",
                name="bedroom",
                footprint_mm=[(float(p[0]), float(p[1])) for p in polygon],
                properties={
                    "number": f"1.0{i}",
                    "polygon_px": polygon,
                    "area_m2": 25,
                    "number_anchor_px": [x, y],
                    "number_alignment": [1, 2],
                },
            )
        )
        if i < 4:  # one room's number was missed by OCR
            tx, ty = 2 * x + 40, 2 * y + 60
            labels.append(
                ExtractedElement(
                    "room_number", "ocr", label=f"1.0{i}", bbox=(tx - 2, ty - 2, tx + 2, ty + 2)
                )
            )
    labels.append(ExtractedElement("room", "ocr", name="old guessed room"))
    raster = ExtractedPage(0, b"original png", 500, 500, 150, None, labels)
    cad = ExtractedPage(0, b"cad rendering", 200, 200, None, 20, rooms)
    return ExtractedDocument(pages=[raster]), ExtractedDocument(pages=[cad])


def test_native_rooms_replace_guesses_and_fill_in_rooms_ocr_missed() -> None:
    raster, cad = _drawings()
    result = fuse_rooms(raster, cad, {"document_id": "cad-id", "filename": "floor.dxf"})
    page = result.pages[0]
    rooms = [e for e in page.elements if e.kind == "room"]
    assert len(rooms) == 4
    assert page.image_png == b"original png"
    assert page.mm_per_px == 10
    assert page.meta["companion_dxf"]["matched_labels"] == 3
    assert all(e.source == "dxf" and e.properties["area_m2"] == 25 for e in rooms)
    for actual, expected in zip(
        rooms[0].properties["polygon_px"], [(50, 70), (70, 70), (70, 90), (50, 90)], strict=True
    ):
        assert actual == pytest.approx(expected)
    assert rooms[0].properties["companion"]["document_id"] == "cad-id"
    assert rooms[-1].properties["number"] == "1.04"
    assert len(raster.pages[0].elements) == 4  # input stays untouched
    assert result.meta["companion_status"] == "matched"


def test_no_reliable_registration_leaves_the_raster_reading_intact() -> None:
    raster, cad = _drawings()
    raster.pages[0].elements = raster.pages[0].elements[:2]
    result = fuse_rooms(raster, cad, {})
    assert result.meta["companion_status"] == "alignment_failed"
    assert result.pages == raster.pages


def test_duplicate_ocr_numbers_do_not_create_false_anchor_pairs() -> None:
    raster, cad = _drawings()
    raster.pages[0].elements.append(raster.pages[0].elements[0])
    assert fuse_rooms(raster, cad, {}).meta["companion_status"] == "alignment_failed"


def test_geometry_outside_the_page_is_not_applied() -> None:
    raster, cad = _drawings()
    cad.pages[0].elements[-1].properties["polygon_px"] = [[500, 500], [600, 500], [600, 600]]
    result = fuse_rooms(raster, cad, {})
    assert result.meta["companion_status"] == "outside_page"
    assert result.pages == raster.pages


def test_multi_page_documents_are_not_matched_to_a_single_floor() -> None:
    raster, cad = _drawings()
    raster = replace(raster, pages=raster.pages * 2)
    assert fuse_rooms(raster, cad, {}).meta["companion_status"] == "multiple_pages"
