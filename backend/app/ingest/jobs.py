"""The ingest job, run by the RQ worker: build (read -> IFC -> index -> mesh), save, publish.

A document never stays `queued` or `processing` after its job ends: every failure is
recorded, including the ones the job can't see itself (see the RQ callbacks below).
"""

import gzip
import json
import logging
import uuid
from typing import Any

from rq.exceptions import AbandonedJobError
from rq.job import Job

from app.config import get_settings
from app.db import session_scope
from app.domain.recovery import IN_FLIGHT
from app.ingest.errors import ReaderError
from app.ingest.persist import replace_contents
from app.ingest.pipeline import build
from app.models import Document
from app.storage import mesh_path, model_ifc_path, original_path, write_bytes
from app.valkey import publish_event

log = logging.getLogger(__name__)


def ingest_document(document_id: str) -> None:
    doc_id = uuid.UUID(document_id)
    try:
        with session_scope() as db:
            doc = db.get(Document, doc_id)
            if doc is None:
                log.warning("ingest: document %s no longer exists", document_id)
                return
            doc.status, doc.error_code = "processing", None
            kind, source = doc.kind, original_path(doc_id, str(doc.meta.get("extension", "")))
        _emit(document_id, "processing", "reading", 0.0)

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
        mark_failed(document_id, code)
        return
    _emit(document_id, "ready", "done", 1.0)


def mark_failed(document_id: str, code: str) -> None:
    """Record that ingesting a document failed. Never raises: it runs while handling a failure.

    Only an in-flight document changes; a finished one keeps its result.
    """
    try:
        with session_scope() as db:
            doc = db.get(Document, uuid.UUID(document_id))
            if doc is None or doc.status not in IN_FLIGHT:
                return
            doc.status, doc.error_code = "failed", code
    except Exception:
        log.exception("could not record that ingesting %s failed", document_id)
        return
    _emit(document_id, "failed", "failed", 1.0)


def on_ingest_failure(job: Job, connection: Any, *exc_info: Any) -> None:
    """RQ failure callback. RQ also calls it when a worker died mid-job (an abandoned job)."""
    abandoned = bool(exc_info) and exc_info[0] is AbandonedJobError
    mark_failed(str(job.args[0]), "ingest_interrupted" if abandoned else "ingest_failed")


def on_work_horse_killed(job: Job, retpid: int, ret_val: int, rusage: Any) -> None:
    """RQ handler for a job process that was killed (e.g. out of memory): no except ran."""
    mark_failed(str(job.args[0]), "ingest_killed")


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
