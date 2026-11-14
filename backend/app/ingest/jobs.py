"""The ingest job, run by the RQ worker: build (read -> IFC -> index -> mesh), save, publish."""

import gzip
import json
import logging
import uuid

from app.config import get_settings
from app.db import session_scope
from app.ingest.errors import ReaderError
from app.ingest.persist import replace_contents
from app.ingest.pipeline import build
from app.models import Document
from app.storage import mesh_path, model_ifc_path, original_path, write_bytes
from app.valkey import publish_event

log = logging.getLogger(__name__)


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

    try:
        built = build(
            source,
            kind,
            get_settings(),
            model_ifc_path(doc_id),
            lambda stage, fraction: _emit(document_id, "processing", stage, round(fraction, 3)),
        )
        if built.mesh is not None:
            raw = json.dumps(built.mesh, separators=(",", ":")).encode()
            write_bytes(mesh_path(doc_id), gzip.compress(raw, compresslevel=6))
        _emit(document_id, "processing", "saving", 0.95)
        with session_scope() as db:
            doc = db.get_one(Document, doc_id)
            count = replace_contents(db, doc, built)
            doc.has_model = built.mesh is not None
            doc.page_count = len(built.pages)
            omitted = built.mesh.get("omitted", 0) if built.mesh else 0
            doc.meta = {**doc.meta, **built.meta, "elements": count, "warnings": built.warnings,
                        "meshes_omitted": omitted}  # fmt: skip
            doc.version += 1
            doc.status = "ready"
    except Exception as exc:
        code = exc.code if isinstance(exc, ReaderError) else "ingest_failed"
        log.exception("ingest failed for %s (%s)", document_id, code)
        with session_scope() as db:
            failed = db.get(Document, doc_id)
            if failed is not None:
                failed.status, failed.error_code = "failed", code
        _emit(document_id, "failed", "failed", 1.0)
        return
    _emit(document_id, "ready", "done", 1.0)


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
