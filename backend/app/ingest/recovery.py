"""On worker start: queue documents again whose ingest job was lost (D-017)."""

import logging
from datetime import datetime

from sqlalchemy import select, update

from app.db import session_scope
from app.domain.recovery import IN_FLIGHT, DocumentState, stranded
from app.models import Document
from app.valkey import enqueue_ingest, in_flight_document_ids, publish_event

log = logging.getLogger(__name__)


def requeue_stranded(now: datetime) -> list[str]:
    """Enqueue a new job for every in-flight document that no job refers to."""
    with_job = in_flight_document_ids()
    with session_scope() as db:
        rows = db.execute(
            select(Document.id, Document.status, Document.created_at).where(
                Document.status.in_(IN_FLIGHT)
            )
        ).all()
        states = [DocumentState(str(r.id), r.status, r.created_at) for r in rows]
        ids = stranded(states, with_job, now)
        if ids:
            db.execute(update(Document).where(Document.id.in_(ids)).values(status="queued"))
    for doc_id in ids:
        enqueue_ingest(doc_id)
        publish_event({"type": "document", "document_id": doc_id, "status": "queued"})
    if ids:
        log.warning("queued %d document(s) again whose ingest job was lost", len(ids))
    return ids
