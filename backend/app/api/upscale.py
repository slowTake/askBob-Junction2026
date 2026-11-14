"""Upscale a plan page on demand (#82).

Raster image pages get the sketch redraw: a strong model authors the whole plan and
checks it in a draw, compare, correct loop (`app/upscale/sketch_service.py`). Every
other format gets one vision pass that adds what ingest missed.
"""

import time
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.domain.sketch import is_sketch_page
from app.envelope import AppError, ok
from app.models import Document, Page
from app.schemas import PageOut
from app.upscale.service import upscale_page
from app.upscale.sketch_model import ask_sketch
from app.upscale.sketch_service import redraw_sketch
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
    "sketch_needs_claude": (
        "Redrawing a sketch needs the Claude model, and the server is set to another one.",
        503,
    ),
    "sketch_unreadable": ("No floor plan could be read from this image.", 422),
    "sketch_failed": ("The sketch could not be redrawn. Try again.", 502),
}
clock = time.time  # replaced in tests


@router.post("/{document_id}/pages/{index}/upscale")
def upscale(document_id: uuid.UUID, index: int, db: DB) -> dict[str, Any]:
    """Synchronous. The gap-filling pass is one bounded model request, and the page row
    is locked for its duration, so a second click waits and gets the cached result.

    The sketch redraw takes minutes: it claims the page under the lock and runs without
    it; a second click meanwhile gets `redraw_running` at once (sketch_service.py).
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
        if is_sketch_page(doc.kind):
            result, page = redraw_sketch(db, doc, page, get_settings(), ask_sketch, clock)
        else:
            result = upscale_page(db, doc, page, get_settings(), find_missing)
    except VisionError as exc:
        message, status = _ERRORS.get(exc.code, _ERRORS["upscale_failed"])
        code = exc.code if exc.code in _ERRORS else "upscale_failed"
        raise AppError(code, message, status) from None
    return ok({**result, "page": PageOut.model_validate(page).model_dump(mode="json")})
