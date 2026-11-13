"""The ingest job, run by the RQ worker: read -> save -> build 3D model -> publish progress."""

import json
import logging
import uuid
from pathlib import Path

from app.bim.ifc_mesh import ifc_to_mesh
from app.bim.ifc_writer import BimItem, write_ifc
from app.config import get_settings
from app.db import session_scope
from app.ingest.persist import replace_contents
from app.ingest.registry import READERS
from app.ingest.types import ExtractedElement
from app.models import Document, Element, Page
from app.storage import mesh_path, model_ifc_path, original_path, write_bytes
from app.valkey import publish_event

log = logging.getLogger(__name__)

Rows = list[tuple[ExtractedElement, Element, Page | None]]


def ingest_document(document_id: str) -> None:
    doc_id = uuid.UUID(document_id)
    with session_scope() as db:
        doc = db.get(Document, doc_id)
        if doc is None:
            log.warning("ingest: document %s no longer exists", document_id)
            return
        doc.status, doc.error_code = "processing", None
        kind, source = doc.kind, original_path(doc_id, str(doc.meta.get("extension", "")))
    _emit(document_id, "processing", "reading", 0.0)

    def progress(stage: str, fraction: float) -> None:
        _emit(document_id, "processing", stage, round(0.7 * fraction, 3))

    try:
        extracted = READERS[kind](source, get_settings(), progress)
        _emit(document_id, "processing", "saving", 0.75)
        with session_scope() as db:
            doc = db.get_one(Document, doc_id)
            rows = replace_contents(db, doc, extracted)
            _emit(document_id, "processing", "modelling", 0.85)
            doc.has_model = _build_model(doc, source, rows)
            doc.page_count = len(extracted.pages)
            doc.meta = {**doc.meta, **extracted.meta}
            doc.version += 1
            doc.status = "ready"
    except Exception:
        log.exception("ingest failed for %s", document_id)
        with session_scope() as db:
            failed = db.get(Document, doc_id)
            if failed is not None:
                failed.status, failed.error_code = "failed", "ingest_failed"
        _emit(document_id, "failed", "failed", 1.0)
        return
    _emit(document_id, "ready", "done", 1.0)


def _build_model(doc: Document, source: Path, rows: Rows) -> bool:
    """IFC uploads: mesh the original. Drawings: write an IFC from what we found, then mesh it."""
    if doc.kind == "ifc":
        ifc_path = source
    else:
        items = [_bim_item(doc, ex, row, page) for ex, row, page in rows]
        items = [i for i in items if i.footprint_mm or i.kind == "door"]
        if not any(i.footprint_mm for i in items):
            return False  # page scale unknown or nothing found: no 3D model yet
        ifc_path = model_ifc_path(doc.id)
        guids = write_ifc(items, ifc_path, project_name=doc.filename)
        for _, row, _ in rows:
            row.ifc_guid = guids.get(str(row.id), row.ifc_guid)  # link 2D element <-> 3D product
    mesh = ifc_to_mesh(ifc_path)
    write_bytes(mesh_path(doc.id), json.dumps(mesh, separators=(",", ":")).encode())
    return True


def _bim_item(doc: Document, ex: ExtractedElement, row: Element, page: Page | None) -> BimItem:
    provenance: dict[str, str | float | int] = {
        "SourceDocument": doc.filename,
        "ElementId": str(row.id),
        "Source": ex.source,
        "Confidence": ex.confidence,
    }
    if page is not None:
        provenance["Page"] = page.index + 1
    if ex.bbox:
        provenance["BBoxPx"] = ",".join(f"{v:.0f}" for v in ex.bbox)
    return BimItem(
        str(row.id), ex.kind, ex.label, ex.name, ex.footprint_mm, ex.value_mm, provenance
    )


def _emit(document_id: str, status: str, stage: str, progress: float) -> None:
    publish_event(
        {
            "type": "document",
            "document_id": document_id,
            "status": status,
            "stage": stage,
            "progress": progress,
        }
    )
