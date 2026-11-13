"""Save a reader's output: page images to storage, pages and elements to Postgres."""

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.ingest.types import ExtractedDocument, ExtractedElement
from app.models import Document, Element, Page
from app.storage import page_image_path, write_bytes


def replace_contents(
    db: Session, doc: Document, extracted: ExtractedDocument
) -> list[tuple[ExtractedElement, Element, Page | None]]:
    """Replace everything previously extracted for `doc` (re-ingest is idempotent)."""
    db.execute(delete(Element).where(Element.document_id == doc.id))
    db.execute(delete(Page).where(Page.document_id == doc.id))
    rows: list[tuple[ExtractedElement, Element, Page | None]] = []

    for page_data in extracted.pages:
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
        rows.extend((ex, _row(doc, page, ex), page) for ex in page_data.elements)

    rows.extend((ex, _row(doc, None, ex), None) for ex in extracted.elements)
    db.add_all(row for _, row, _ in rows)
    db.flush()  # assigns element ids
    return rows


def _row(doc: Document, page: Page | None, ex: ExtractedElement) -> Element:
    return Element(
        document_id=doc.id,
        page_id=page.id if page else None,
        kind=ex.kind,
        text=ex.text,
        label=ex.label,
        name=ex.name,
        value_mm=ex.value_mm,
        bbox=[round(v, 1) for v in ex.bbox] if ex.bbox else None,
        footprint_mm=[[round(x, 1), round(y, 1)] for x, y in ex.footprint_mm]
        if ex.footprint_mm
        else None,
        ifc_guid=ex.ifc_guid,
        properties=ex.properties,
        source=ex.source,
        confidence=ex.confidence,
    )
