"""Save a built document: page images to storage, pages and elements to Postgres."""

import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.domain.text import clip
from app.ingest.pipeline import BuiltDocument
from app.ingest.types import ExtractedElement
from app.models import LABEL_MAX, NAME_MAX, Document, Element, Page
from app.storage import page_image_path, write_bytes


def replace_contents(db: Session, doc: Document, built: BuiltDocument) -> int:
    """Replace everything previously stored for `doc` (re-ingest is idempotent).

    Returns the number of elements stored.
    """
    db.execute(delete(Element).where(Element.document_id == doc.id))
    db.execute(delete(Page).where(Page.document_id == doc.id))

    page_ids: dict[int, uuid.UUID] = {}
    for page_data in built.pages:
        write_bytes(page_image_path(doc.id, page_data.index), page_data.image_png)
        page = Page(
            document_id=doc.id,
            index=page_data.index,
            width_px=page_data.width_px,
            height_px=page_data.height_px,
            dpi=page_data.dpi,
            mm_per_px=page_data.mm_per_px,
            meta=page_data.meta,
        )
        db.add(page)
        db.flush()  # assigns page.id
        page_ids[page_data.index] = page.id

    rows = [_row(doc, page_ids, el) for el in built.elements]
    db.add_all(rows)
    db.flush()
    return len(rows)


def _row(doc: Document, page_ids: dict[int, uuid.UUID] | None, el: ExtractedElement) -> Element:
    return Element(
        document_id=doc.id,
        page_id=(page_ids or {}).get(el.page_index) if el.page_index is not None else None,
        kind=el.kind,
        text=el.text,
        label=clip(el.label, LABEL_MAX),  # one long token must not fail the whole document
        name=clip(el.name, NAME_MAX),
        value_mm=el.value_mm,
        bbox=[round(v, 1) for v in el.bbox] if el.bbox else None,
        footprint_mm=[[round(x, 1), round(y, 1)] for x, y in el.footprint_mm]
        if el.footprint_mm
        else None,
        ifc_guid=el.ifc_guid,
        properties=el.properties,
        source=el.source,
        confidence=el.confidence,
    )
