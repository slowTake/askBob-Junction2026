import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.ingest_errors import MESSAGES
from app.schemas import MAX_SELECTED, AskContextIn, DocumentOut, PageOut


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


def test_page_label_is_the_storey() -> None:
    page = {"id": uuid.uuid4(), "index": 0, "width_px": 10, "height_px": 10, "dpi": None,
            "mm_per_px": None, "meta": {"storey": "Level 1", "words": 3}}  # fmt: skip
    dumped = PageOut.model_validate(page).model_dump()
    assert dumped["label"] == "Level 1" and "meta" not in dumped


# What the user selected on the plan, as the ask request carries it.
A, B, C = (uuid.UUID(int=n) for n in (1, 2, 3))


def test_selected_ids_keep_click_order_without_duplicates() -> None:
    context = AskContextIn(element_ids=[B, A, B, C])
    assert context.selected_ids() == [B, A, C]


def test_a_single_element_id_still_works() -> None:
    # Older clients send one clicked element as element_id.
    assert AskContextIn(element_id=A).selected_ids() == [A]
    assert AskContextIn(element_id=A, element_ids=[B]).selected_ids() == [B, A]
    assert AskContextIn().selected_ids() == []


def test_too_many_selected_elements_are_refused() -> None:
    ids = [uuid.UUID(int=n) for n in range(MAX_SELECTED + 1)]
    with pytest.raises(ValidationError):
        AskContextIn(element_ids=ids)
    assert len(AskContextIn(element_ids=ids[:MAX_SELECTED]).selected_ids()) == MAX_SELECTED


def test_page_says_whether_it_was_upscaled() -> None:
    page = {"id": uuid.uuid4(), "index": 0, "width_px": 10, "height_px": 10, "dpi": None,
            "mm_per_px": None, "meta": {}}  # fmt: skip
    assert PageOut.model_validate(page).model_dump()["upscale"] is None
    page["meta"] = {"upscale": {"document_version": 2, "format": 1, "model": "m", "added": 4,
                                "input_tokens": 3000, "output_tokens": 400}}  # fmt: skip
    # Only what the UI shows; the token counts stay on the server.
    assert PageOut.model_validate(page).model_dump()["upscale"] == {"added": 4, "model": "m"}
