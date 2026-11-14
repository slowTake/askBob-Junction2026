"""Decide which reader handles an uploaded file."""

from typing import Literal

DocumentKind = Literal["ifc", "pdf", "image", "dxf"]

_EXTENSIONS: dict[str, DocumentKind] = {
    ".ifc": "ifc",
    ".dxf": "dxf",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tif": "image",
    ".tiff": "image",
}

_MAGIC: list[tuple[bytes, DocumentKind]] = [
    (b"%PDF", "pdf"),
    (b"\x89PNG", "image"),
    (b"\xff\xd8\xff", "image"),
    (b"II*\x00", "image"),
    (b"MM\x00*", "image"),
    (b"ISO-10303-21", "ifc"),
    (b"0\nSECTION", "dxf"),
    (b"0\r\nSECTION", "dxf"),
]


def detect_kind(filename: str, head: bytes) -> DocumentKind | None:
    """Return the document kind, or None when the file is unsupported.

    The file content (magic bytes) wins over the extension, so a renamed file is
    still read correctly. The extension is only a fallback for unknown content.
    """
    stripped = head.lstrip()
    for magic, kind in _MAGIC:
        if stripped.startswith(magic):
            return kind
    dot = filename.rfind(".")
    if dot == -1:
        return None
    return _EXTENSIONS.get(filename[dot:].lower())


def extension_for(kind: DocumentKind, filename: str) -> str:
    """Extension used to store the original file."""
    dot = filename.rfind(".")
    ext = filename[dot:].lower() if dot != -1 else ""
    if ext in _EXTENSIONS and _EXTENSIONS[ext] == kind:
        return ext
    return {"ifc": ".ifc", "pdf": ".pdf", "image": ".png", "dxf": ".dxf"}[kind]
