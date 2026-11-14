"""One reader per document kind. Add a format: write a reader, register it here."""

from collections.abc import Callable
from pathlib import Path

from app.config import Settings
from app.ingest.dxf_reader import read_dxf
from app.ingest.ifc_reader import read_ifc
from app.ingest.image_reader import read_image
from app.ingest.pdf_reader import read_pdf
from app.ingest.types import ExtractedDocument, Progress

Reader = Callable[[Path, Settings, Progress], ExtractedDocument]

READERS: dict[str, Reader] = {
    "ifc": read_ifc,
    "pdf": read_pdf,
    "image": read_image,
    "dxf": read_dxf,
}
