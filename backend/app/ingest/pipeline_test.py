"""Every supported format goes through the same pipeline and comes out in the same shape."""

import shutil
from pathlib import Path

import ezdxf
import pymupdf
import pytest
from PIL import Image, ImageDraw

from app.bim.ifc_writer import write_model
from app.config import Settings
from app.ingest.errors import ReaderError
from app.ingest.pipeline import BuiltDocument, build
from app.ingest.types import ExtractedElement

SETTINGS = Settings(database_url="x", valkey_url="x", ocr_langs="eng")
needs_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="no tesseract")


def _build(path: Path, kind: str, tmp: Path) -> BuiltDocument:
    return build(path, kind, SETTINGS, tmp / "model.ifc", lambda stage, f: None)


def _same_shape(built: BuiltDocument) -> None:
    """What every format must give the rest of the app."""
    assert built.model_path is not None and built.model_path.is_file()
    assert built.elements, "something was found"
    assert all(e.ifc_guid for e in built.elements), "every element has an IFC id (3D link)"
    assert all(0.0 <= e.confidence <= 1.0 for e in built.elements)
    pages = {p.index for p in built.pages}
    assert all(e.page_index in pages for e in built.elements if e.page_index is not None)


def _dxf(path: Path) -> None:
    doc = ezdxf.new(units=6)  # metres, like the dataset's Swiss DXFs
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (4, 0), (4, 3), (0, 3)], close=True, dxfattribs={"layer": "ROOM_OUTLINE"}
    )
    msp.add_lwpolyline(
        [(0, -0.2), (4, -0.2), (4, 0), (0, 0)], close=True, dxfattribs={"layer": "WALL"}
    )
    msp.add_text("Zimmer", dxfattribs={"layer": "ROOM_TEXT", "insert": (1, 1.5), "height": 0.3})
    msp.add_text("2.01", dxfattribs={"layer": "ROOM_TEXT", "insert": (1, 1.0), "height": 0.3})
    doc.saveas(path)


def _pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    page.draw_rect(pymupdf.Rect(100, 100, 300, 250), width=4)
    page.insert_text((180, 170), "Zimmer", fontsize=10)
    page.insert_text((185, 185), "2.01", fontsize=10)
    page.insert_text((600, 550), "Massstab 1:50", fontsize=10)
    doc.save(path)


def test_dxf(tmp_path: Path) -> None:
    _dxf(tmp_path / "plan.dxf")
    built = _build(tmp_path / "plan.dxf", "dxf", tmp_path)
    _same_shape(built)
    (room,) = [e for e in built.elements if e.kind == "room"]
    assert room.text == "Zimmer" and room.properties["number"] == "2.01"
    assert room.properties["area_m2"] == 12.0  # 4 m x 3 m outline
    assert built.mesh is not None  # walls and rooms have real geometry


def test_pdf(tmp_path: Path) -> None:
    _pdf(tmp_path / "plan.pdf")
    built = _build(tmp_path / "plan.pdf", "pdf", tmp_path)
    _same_shape(built)
    assert len(built.pages) == 1 and built.pages[0].mm_per_px is not None  # scale from "1:50"
    room = next(e for e in built.elements if e.kind == "room")
    assert room.properties["number"] == "2.01" and room.page_index == 0


def test_svg(tmp_path: Path) -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">'
        '<rect x="20" y="20" width="300" height="200" fill="none" stroke="black" stroke-width="6"/>'
        '<text x="120" y="120" font-size="14">Cuisine</text>'
        '<text x="125" y="140" font-size="14">1.07</text>'
        "</svg>"
    )
    (tmp_path / "plan.svg").write_text(svg)
    built = _build(tmp_path / "plan.svg", "svg", tmp_path)
    _same_shape(built)
    assert any(e.kind == "room" and e.text == "Cuisine" for e in built.elements)


def test_ifc_upload_is_its_own_model(tmp_path: Path) -> None:
    write_model(
        [ExtractedElement("door", "ifc", label="D1", value_mm=900)], tmp_path / "in.ifc", "p"
    )
    built = _build(tmp_path / "in.ifc", "ifc", tmp_path)
    _same_shape(built)
    assert built.model_path == tmp_path / "in.ifc" and built.pages == []


@needs_tesseract
def test_png_and_multipage_tiff(tmp_path: Path) -> None:
    image = Image.new("RGB", (900, 600), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 100, 700, 500), outline="black", width=8)
    image.save(tmp_path / "plan.png")
    built = _build(tmp_path / "plan.png", "image", tmp_path)
    _same_shape(built)
    image.save(tmp_path / "set.tif", save_all=True, append_images=[image])
    assert len(_build(tmp_path / "set.tif", "image", tmp_path).pages) == 2


def test_damaged_files_fail_with_a_reason(tmp_path: Path) -> None:
    (tmp_path / "bad.pdf").write_bytes(b"%PDF-1.7 this is not really a pdf")
    with pytest.raises(ReaderError) as pdf_error:
        _build(tmp_path / "bad.pdf", "pdf", tmp_path)
    assert pdf_error.value.code in ("unreadable_file", "empty_drawing")
    (tmp_path / "bad.png").write_bytes(b"\x89PNG broken")
    with pytest.raises(ReaderError) as png_error:
        _build(tmp_path / "bad.png", "image", tmp_path)
    assert png_error.value.code == "unreadable_file"


@pytest.mark.skipif(shutil.which("dwg2dxf") is not None, reason="a DWG converter is installed")
def test_dwg_without_converter_says_so(tmp_path: Path) -> None:
    (tmp_path / "plan.dwg").write_bytes(b"AC1032" + b"\x00" * 64)
    with pytest.raises(ReaderError) as error:
        _build(tmp_path / "plan.dwg", "dwg", tmp_path)
    assert error.value.code in ("dwg_converter_missing", "unreadable_file")


def test_dxf_with_meaningless_layers_falls_back_to_vision(tmp_path: Path) -> None:
    # Like opening_design's "Site plan.dxf": everything on one layer that says nothing.
    doc = ezdxf.new(units=6)
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (4, 0), (4, 3), (0, 3)], close=True, dxfattribs={"layer": "Site plan"}
    )
    msp.add_text("Kitchen", dxfattribs={"layer": "Site plan", "insert": (1.2, 1.4), "height": 0.25})
    doc.saveas(tmp_path / "plan.dxf")
    built = _build(tmp_path / "plan.dxf", "dxf", tmp_path)
    _same_shape(built)
    assert built.pages[0].meta["layers_meaningful"] is False
    (room,) = [e for e in built.elements if e.kind == "room"]
    # Traced inside a 4 m x 3 m outline drawn with 2 px lines: 12 m² minus the line width.
    assert room.text == "Kitchen" and 11.0 < room.properties["area_m2"] <= 12.0
