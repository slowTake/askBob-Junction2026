"""One reader per document kind. Add a format: write a reader, register it here.

IFC has no reader: an IFC upload is already the model (see pipeline.py).
"""

from collections.abc import Callable
from pathlib import Path

from app.config import Settings
from app.ingest.dwg_reader import read_dwg
from app.ingest.dxf_reader import read_dxf
from app.ingest.image_reader import read_image
from app.ingest.pdf_reader import read_pdf
from app.ingest.types import ExtractedDocument, Progress

Reader = Callable[[Path, Settings, Progress], ExtractedDocument]

READERS: dict[str, Reader] = {
    "pdf": read_pdf,
    "svg": read_pdf,  # PyMuPDF renders SVG and exposes its text and paths like a PDF page
    "image": read_image,
    "dxf": read_dxf,
    "dwg": read_dwg,
}
