"""Upscale a plan page on demand (#82): one vision pass that adds what ingest missed."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.envelope import AppError, ok
from app.models import Document, Page
from app.schemas import PageOut
from app.upscale.service import upscale_page
from app.upscale.vision import VisionError, find_missing

router = APIRouter(prefix="/api/documents", tags=["upscale"])
DB = Annotated[Session, Depends(get_db)]

# code -> (message written for users, HTTP status). The raw error stays in the log.
_ERRORS = {
    "llm_not_configured": ("The language model is not configured on the server.", 503),
    "llm_busy": ("The language model is busy. Try again in a minute.", 503),
    "llm_unavailable": ("The language model is unavailable right now.", 502),
    "refused": ("The model declined to read this page.", 502),
    "upscale_failed": ("The page could not be upscaled. Try again.", 502),
}


@router.post("/{document_id}/pages/{index}/upscale")
def upscale(document_id: uuid.UUID, index: int, db: DB) -> dict[str, Any]:
    """Synchronous and bounded: one model request with a timeout, then a small insert.

    The page row is locked for the duration, so two clicks never add the same
    elements twice; the second one waits and gets the cached result.
    """
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("not_found", "Document not found", 404)
    if doc.status != "ready":
        raise AppError("not_ready", "The document is still being processed.", 409)
    page = db.scalar(
        select(Page)
        .where(Page.document_id == document_id, Page.index == index)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if page is None:
        raise AppError("not_found", "Page not found", 404)
    try:
        result = upscale_page(db, doc, page, get_settings(), find_missing)
    except VisionError as exc:
        message, status = _ERRORS.get(exc.code, _ERRORS["upscale_failed"])
        code = exc.code if exc.code in _ERRORS else "upscale_failed"
        raise AppError(code, message, status) from None
    return ok({**result, "page": PageOut.model_validate(page).model_dump(mode="json")})
