"""Upload, list and inspect documents; serve page images, the IFC model and its mesh."""

import hashlib
import logging
import shutil
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import get_db
from app.domain.files import detect_kind, extension_for
from app.envelope import AppError, ok
from app.models import Document, Element, Page
from app.schemas import DocumentDetailOut, DocumentOut, ElementOut
from app.storage import document_dir, mesh_path, model_ifc_path, original_path, page_image_path
from app.valkey import QueueError, enqueue_ingest, publish_event

router = APIRouter(prefix="/api/documents", tags=["documents"])
DB = Annotated[Session, Depends(get_db)]
CHUNK = 1024 * 1024
log = logging.getLogger(__name__)


@router.get("")
def list_documents(db: DB) -> dict[str, Any]:
    docs = db.scalars(select(Document).order_by(Document.created_at.desc())).all()
    return ok([DocumentOut.model_validate(d).model_dump(mode="json") for d in docs])


@router.post("")
def upload_document(file: UploadFile, db: DB) -> dict[str, Any]:
    filename = Path(file.filename or "upload").name
    head = file.file.read(64)
    if not head:
        raise AppError("empty_file", "The file is empty")
    kind = detect_kind(filename, head)
    if kind is None:
        raise AppError("unsupported_file", "Upload an IFC, PDF, PNG, JPEG or TIFF file")
    file.file.seek(0)

    doc_id = uuid.uuid4()
    extension = extension_for(kind, filename)
    target = original_path(doc_id, extension)
    target.parent.mkdir(parents=True, exist_ok=True)
    limit = get_settings().max_upload_mb * 1024 * 1024
    digest, size = hashlib.sha256(), 0
    with target.open("wb") as out:
        while chunk := file.file.read(CHUNK):
            size += len(chunk)
            if size > limit:
                out.close()
                shutil.rmtree(document_dir(doc_id), ignore_errors=True)
                raise AppError("too_large", "File is larger than the upload limit", 413)
            digest.update(chunk)
            out.write(chunk)

    doc = Document(
        id=doc_id,
        filename=filename,
        kind=kind,
        status="queued",
        sha256=digest.hexdigest(),
        size_bytes=size,
        meta={"extension": extension},
    )
    db.add(doc)
    db.commit()
    try:
        _queue(doc)
    except QueueError:
        # D-010: never leave a document "queued" without a job. Undo the upload.
        log.warning("upload %s: queue unavailable, rolling back", doc_id, exc_info=True)
        db.delete(doc)
        db.commit()
        shutil.rmtree(document_dir(doc_id), ignore_errors=True)
        raise _queue_unavailable() from None
    return ok(DocumentOut.model_validate(doc).model_dump(mode="json"))


@router.get("/{document_id}")
def get_document(document_id: uuid.UUID, db: DB) -> dict[str, Any]:
    doc = db.scalar(
        select(Document).where(Document.id == document_id).options(selectinload(Document.pages))
    )
    if doc is None:
        raise AppError("not_found", "Document not found", 404)
    return ok(DocumentDetailOut.model_validate(doc).model_dump(mode="json"))


@router.post("/{document_id}/reingest")
def reingest(document_id: uuid.UUID, db: DB) -> dict[str, Any]:
    doc = _document(db, document_id)
    previous = doc.status
    doc.status = "queued"
    db.commit()
    try:
        _queue(doc)
    except QueueError:
        log.warning("reingest %s: queue unavailable", document_id, exc_info=True)
        doc.status = previous
        db.commit()
        raise _queue_unavailable() from None
    return ok(DocumentOut.model_validate(doc).model_dump(mode="json"))


@router.delete("/{document_id}")
def delete_document(document_id: uuid.UUID, db: DB) -> dict[str, Any]:
    doc = _document(db, document_id)
    db.delete(doc)
    db.commit()
    shutil.rmtree(document_dir(document_id), ignore_errors=True)
    publish_event({"type": "document", "document_id": str(document_id), "status": "deleted"})
    return ok({"id": str(document_id)})


@router.get("/{document_id}/elements")
def list_elements(
    document_id: uuid.UUID,
    db: DB,
    page: Annotated[int | None, Query(ge=0)] = None,
    kind: str | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 2000,
) -> dict[str, Any]:
    query = select(Element).where(Element.document_id == document_id)
    if page is not None:
        query = query.join(Page).where(Page.index == page)
    if kind:
        query = query.where(Element.kind == kind)
    rows = db.scalars(query.limit(limit)).all()
    return ok([ElementOut.model_validate(e).model_dump(mode="json") for e in rows])


@router.get("/{document_id}/file")
def original_file(document_id: uuid.UUID, db: DB) -> FileResponse:
    doc = _document(db, document_id)
    path = original_path(doc.id, str(doc.meta.get("extension", "")))
    return FileResponse(_existing(path), filename=doc.filename)


@router.get("/{document_id}/pages/{index}/image")
def page_image(document_id: uuid.UUID, index: int) -> FileResponse:
    return FileResponse(_existing(page_image_path(document_id, index)), media_type="image/png")


@router.get("/{document_id}/model.ifc")
def model_ifc(document_id: uuid.UUID, db: DB) -> FileResponse:
    doc = _document(db, document_id)
    if doc.kind == "ifc":
        path = original_path(doc.id, str(doc.meta.get("extension", ".ifc")))
    else:
        path = model_ifc_path(doc.id)
    stem = Path(doc.filename).stem
    return FileResponse(_existing(path), media_type="application/x-step", filename=f"{stem}.ifc")


@router.get("/{document_id}/mesh")
def mesh(document_id: uuid.UUID) -> FileResponse:
    return FileResponse(_existing(mesh_path(document_id)), media_type="application/json")


def _document(db: Session, document_id: uuid.UUID) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("not_found", "Document not found", 404)
    return doc


def _existing(path: Path) -> Path:
    if not path.is_file():
        raise AppError("not_found", "File not available", 404)
    return path


def _queue_unavailable() -> AppError:
    return AppError(
        "queue_unavailable", "Processing is unavailable right now. Try again in a minute.", 503
    )


def _queue(doc: Document) -> None:
    enqueue_ingest(str(doc.id))
    publish_event(
        {"type": "document", "document_id": str(doc.id), "status": "queued", "progress": 0}
    )
