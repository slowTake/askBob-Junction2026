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
