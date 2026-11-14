"""Load uploaded CAD companions and refresh raster drawings when either file arrives."""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.domain.companions import Candidate, companion_matches, matching_id
from app.ingest.dxf_reader import read_dxf
from app.ingest.types import ExtractedDocument
from app.models import Document
from app.storage import original_path
from app.valkey import QueueError, enqueue_ingest, publish_event

log = logging.getLogger(__name__)


@dataclass
class Companion:
    data: ExtractedDocument | None
    info: dict[str, Any]


def _matching_cad(db: Any, filename: str) -> Document | None:
    candidates = list(db.scalars(select(Document).where(Document.kind == "dxf")))
    chosen = matching_id(
        filename, [Candidate(str(d.id), d.filename, d.sha256, d.status) for d in candidates]
    )
    return next((d for d in candidates if str(d.id) == chosen), None)


def load_companion(document_id: uuid.UUID) -> Companion | None:
    with session_scope() as db:
        doc = db.get(Document, document_id)
        if doc is None or doc.kind != "image":
            return None
        cad = _matching_cad(db, doc.filename)
        if cad is None:
            return None
        info = {"document_id": str(cad.id), "filename": cad.filename, "sha256": cad.sha256}
        path = original_path(cad.id, str(cad.meta.get("extension", ".dxf")))
    try:
        return Companion(read_dxf(path, get_settings(), lambda *_: None), info)
    except Exception:
        log.warning("could not read uploaded CAD companion for %s", document_id, exc_info=True)
        return Companion(None, info)


def refresh_companion_images(document_id: uuid.UUID) -> None:
    """Either upload order works, including a DXF arriving while a PNG is processing.

    Each image checks again on completion. An attempted companion hash is stored
    even when alignment fails, so a bad match cannot create an endless job loop.
    """
    with session_scope() as db:
        source = db.get(Document, document_id)
        if source is None or source.kind not in ("image", "dxf"):
            return
        ids = [d.id for d in db.scalars(select(Document).where(Document.kind == "image"))
               if companion_matches(source.filename, d.filename)]  # fmt: skip
    for image_id in ids:
        with session_scope() as db:
            image = db.scalar(select(Document).where(Document.id == image_id).with_for_update())
            if image is None or image.status != "ready":
                continue
            cad = _matching_cad(db, image.filename)
            attempted = image.meta.get("companion_attempt", {})
            if cad is None or attempted.get("sha256") == cad.sha256:
                continue
            try:
                # Keep the row locked until its queued status is committed. A
                # worker may start immediately; it waits for this short transaction.
                enqueue_ingest(str(image_id))
            except QueueError:
                log.warning("could not refresh image companion for %s", image_id, exc_info=True)
                continue
            image.status = "queued"
        publish_event({"type": "document", "document_id": str(image_id), "status": "queued"})
