from app.domain.files import detect_kind, extension_for


def test_magic_bytes_win_over_extension() -> None:
    # A PDF header starts with "%PDF" (PDF 1.7 spec, 7.5.2).
    assert detect_kind("plan.png", b"%PDF-1.7\n") == "pdf"


def test_ifc_header_with_leading_whitespace() -> None:
    # STEP files start with "ISO-10303-21;" (ISO 10303-21, clause 5).
    assert detect_kind("model.ifc", b"\n ISO-10303-21;\nHEADER;") == "ifc"


def test_png_and_jpeg_magic() -> None:
    assert detect_kind("x", b"\x89PNG\r\n\x1a\n") == "image"
    assert detect_kind("x", b"\xff\xd8\xff\xe0") == "image"


def test_extension_fallback_is_case_insensitive() -> None:
    assert detect_kind("PLAN.JPEG", b"????") == "image"


def test_unsupported_file() -> None:
    assert detect_kind("notes.docx", b"PK\x03\x04") is None
    assert detect_kind("no_extension", b"") is None


def test_extension_for_keeps_matching_extension() -> None:
    assert extension_for("image", "scan.JPG") == ".jpg"


def test_extension_for_replaces_mismatching_extension() -> None:
    assert extension_for("pdf", "plan.png") == ".pdf"


def test_dxf_by_header_or_extension() -> None:
    # ASCII DXF files start with group code 0 and "SECTION" (DXF reference, file structure).
    assert detect_kind("x.bin", b"  0\nSECTION\n  2\nHEADER") == "dxf"
    assert detect_kind("x.bin", b"0\r\nSECTION\r\n") == "dxf"
    assert detect_kind("plan.DXF", b"999\ncomment") == "dxf"
    assert extension_for("dxf", "plan.dxf") == ".dxf"


def test_svg_by_content_even_after_an_xml_prolog() -> None:
    head = b'<?xml version="1.0" encoding="UTF-8"?>\n<!-- exported -->\n<svg xmlns="http://www.w3.org/2000/svg">'
    assert detect_kind("plan.bin", head) == "svg"
    assert detect_kind("plan.svg", b"") == "svg"
    assert extension_for("svg", "a.svg") == ".svg"


def test_dwg_by_version_magic() -> None:
    # DWG files start with "AC10" + two version digits (AC1032 = AutoCAD 2018 format).
    assert detect_kind("x.bin", b"AC1032\x00\x00") == "dwg"
    assert detect_kind("PLAN.DWG", b"????") == "dwg"


def test_more_raster_formats() -> None:
    assert detect_kind("x", b"RIFF\x24\x00\x00\x00WEBPVP8 ") == "image"  # RIFF....WEBP
    assert detect_kind("x", b"GIF89a") == "image"
    assert detect_kind("x.bmp", b"BM6\x00") == "image"


def test_an_xml_file_that_is_not_svg_is_not_svg() -> None:
    assert detect_kind("data.xml", b'<?xml version="1.0"?><root/>') is None
