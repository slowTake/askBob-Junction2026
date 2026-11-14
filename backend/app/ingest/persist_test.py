import uuid

from app.ingest.persist import _row
from app.ingest.types import ExtractedElement
from app.models import LABEL_MAX, NAME_MAX, Document


def test_long_label_and_name_fit_their_columns() -> None:
    """A 300-character token (dot leaders, URLs) must not fail the whole ingest (#5)."""
    doc = Document(id=uuid.uuid4())
    token = "x" * 300
    long_name = "n" * 600
    row = _row(doc, None, ExtractedElement("text", "pdf_text", token, token, long_name))
    assert LABEL_MAX == 256 and NAME_MAX == 512  # the column sizes in models.py
    assert row.label == "x" * 255 + "…"  # 255 kept + ellipsis = 256
    assert row.name == "n" * 511 + "…"  # 511 kept + ellipsis = 512
    assert row.text == token  # the raw text column is unbounded and keeps everything


def test_short_label_is_stored_as_is() -> None:
    row = _row(Document(id=uuid.uuid4()), None, ExtractedElement("room", "pdf_text", "MH", "MH"))
    assert row.label == "MH"
