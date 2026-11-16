import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.domain.ingest_errors import MESSAGES
from app.domain.upscale import UPSCALE_FORMAT
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
    page["meta"] = {"upscale": {"document_version": 2, "format": UPSCALE_FORMAT, "model": "m",
                                "added": 4, "input_tokens": 3000,
                                "output_tokens": 400}}  # fmt: skip
    # Only what the UI shows; the token counts stay on the server. No mode: an entry
    # written before the sketch redraw was a gap-filling pass.
    assert PageOut.model_validate(page).model_dump()["upscale"] == {
        "added": 4, "model": "m", "mode": "fill", "rounds": None,
    }  # fmt: skip


def test_a_sketch_redraw_says_so_and_how_many_rounds_it_took() -> None:
    entry = {"document_version": 2, "format": UPSCALE_FORMAT, "mode": "sketch", "model": "m",
             "added": 30, "rounds": 2, "matched": True}  # fmt: skip
    page = {"id": uuid.uuid4(), "index": 0, "width_px": 10, "height_px": 10, "dpi": None,
            "mm_per_px": None, "meta": {"upscale": entry}}  # fmt: skip
    assert PageOut.model_validate(page).model_dump()["upscale"] == {
        "added": 30, "model": "m", "mode": "sketch", "rounds": 2,
    }  # fmt: skip


def test_a_page_upscaled_in_an_older_format_offers_upscale_again() -> None:
    # The server reruns such a page (is_cached), so the UI must show the button again.
    old = {"document_version": 2, "format": UPSCALE_FORMAT - 1, "model": "m", "added": 0}
    page = {"id": uuid.uuid4(), "index": 0, "width_px": 10, "height_px": 10, "dpi": None,
            "mm_per_px": None, "meta": {"upscale": old}}  # fmt: skip
    assert PageOut.model_validate(page).model_dump()["upscale"] is None


def _page_of(kind: str | None, meta: dict[str, object]) -> object:
    """A page row as the ORM gives it: its document's kind is one attribute away."""
    document = SimpleNamespace(kind=kind) if kind else None
    return SimpleNamespace(id=uuid.uuid4(), index=0, width_px=10, height_px=10, dpi=None,
                           mm_per_px=None, meta=meta, document=document)  # fmt: skip


def test_a_page_says_which_redraw_it_gets() -> None:
    napkin = {"straight_share": 0.1, "fill_share": 0.0, "dimension_words": 0,
              "paper_spread": 40.0}  # fmt: skip
    printed = {**napkin, "fill_share": 0.5}  # colour fills: a printed plan
    assert PageOut.model_validate(_page_of("image", {"page_stats": napkin})).redraw_mode == (
        "sketch"
    )
    dumped = PageOut.model_validate(_page_of("image", {"page_stats": printed})).model_dump()
    assert dumped["redraw_mode"] == "plan"
    assert "document_kind" not in dumped  # only what it decides is sent
    # Ingested before #138: images are sketches, everything else a plan, as before.
    assert PageOut.model_validate(_page_of("image", {})).redraw_mode == "sketch"
    assert PageOut.model_validate(_page_of("pdf", {})).redraw_mode == "plan"


def test_a_page_without_its_document_is_a_plan() -> None:
    # Built from a dict (tests, older callers): no kind, so not a raster image page.
    page = {"id": uuid.uuid4(), "index": 0, "width_px": 10, "height_px": 10, "dpi": None,
            "mm_per_px": None, "meta": {}}  # fmt: skip
    assert PageOut.model_validate(page).redraw_mode == "plan"
    assert PageOut.model_validate({**page, "document_kind": "image"}).redraw_mode == "sketch"
