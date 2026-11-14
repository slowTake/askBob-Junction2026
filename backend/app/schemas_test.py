import uuid
from datetime import UTC, datetime

from app.domain.ingest_errors import MESSAGES
from app.schemas import DocumentOut


def _doc(**overrides: object) -> DocumentOut:
    fields: dict[str, object] = {
        "id": uuid.uuid4(), "filename": "plan.pdf", "kind": "pdf", "status": "ready",
        "page_count": 1, "has_model": False, "size_bytes": 1, "error_code": None,
        "created_at": datetime(2026, 11, 14, tzinfo=UTC), "meta": {"model": {}},
    }  # fmt: skip
    fields.update(overrides)
    return DocumentOut.model_validate(fields)


def test_failed_document_explains_why() -> None:
    doc = _doc(status="failed", error_code="encrypted_pdf", meta={})
    assert doc.model_dump()["error_message"] == MESSAGES["encrypted_pdf"]
    assert doc.has_ifc is False


def test_drawing_with_built_model_offers_ifc() -> None:
    assert _doc().has_ifc is True
    assert _doc(meta={}).has_ifc is False  # IFC writing failed: nothing to download
    assert _doc(kind="ifc", meta={}).has_ifc is True
