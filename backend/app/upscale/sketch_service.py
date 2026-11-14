"""Redraw a sketch page (#82): claim the page, run the loop, store the plan.

The loop makes several calls to a large model and can take minutes, so no row lock or
transaction is held while it runs:

1. Under the page's row lock: serve the cached result, or refuse while another run's
   claim is live, or write our claim (a random token and the start time). Commit.
2. Run the loop with no transaction open.
3. Under the row lock again: if our claim still stands and the document version is
   unchanged, replace the page's model-made elements, cache the result and drop the
   claim. Commit.

A failure anywhere drops our claim and stores nothing, so the next click runs again.
A run that dies without dropping it (a killed process) leaves a claim that goes
stale after the longest a run can take.
"""

import io
import logging
import uuid
from collections.abc import Callable
from typing import Any

from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.sketch import (
    SKETCH_CONFIDENCE,
    SKETCH_MODE,
    SKETCH_SOURCE,
    claim_is_live,
    sketch_cache_entry,
)
from app.domain.sketch_drawing import Shape
from app.domain.sketch_text import Word
from app.domain.text import clip
from app.domain.upscale import UPSCALE_SOURCE, image_scale, is_cached
from app.envelope import AppError
from app.models import LABEL_MAX, NAME_MAX, Document, Element, Page
from app.storage import page_image_path
from app.upscale.sketch_loop import Redraw, run_loop
from app.upscale.sketch_model import SketchAsk
from app.upscale.sketch_render import ink_box, render_png
from app.upscale.vision import Look

log = logging.getLogger(__name__)

RUN_KEY = "sketch_run"  # page.meta key of a running redraw's claim
SketchAsker = Callable[[SketchAsk, Settings], Look]
Clock = Callable[[], float]  # seconds since the epoch: claims are compared across processes


def redraw_sketch(
    db: Session, doc: Document, page: Page, settings: Settings, ask: SketchAsker, now: Clock
) -> tuple[dict[str, Any], Page]:
    """`page` must be locked by the caller. Raises AppError or VisionError on failure."""
    entry = page.meta.get("upscale")
    if is_cached(page.meta, doc.version, SKETCH_MODE) and isinstance(entry, dict):
        return _result(entry, cached=True), page
    if claim_is_live(page.meta.get(RUN_KEY), now(), stale_after(settings)):
        raise AppError(
            "redraw_running",
            "This page is already being redrawn. That takes a few minutes; try again shortly.",
            409,
        )
    path = page_image_path(doc.id, page.index)
    if not path.is_file():
        raise AppError("not_found", "File not available", 404)

    scale = image_scale(page.width_px, page.height_px, settings.sketch_max_side)
    width = max(1, round(page.width_px * scale))
    height = max(1, round(page.height_px * scale))
    with Image.open(path) as image:
        buffer = io.BytesIO()
        image.convert("RGB").resize((width, height)).save(buffer, format="PNG")
    photo = buffer.getvalue()
    words = _words(db, page)
    token = uuid.uuid4().hex
    page.meta = {**page.meta, RUN_KEY: {"token": token, "started_s": now()}}
    ids, version = (doc.id, page.id), doc.version
    page_w, page_h = float(page.width_px), float(page.height_px)
    db.commit()  # the claim is visible to other requests; the row lock is released

    deadline = now() + settings.sketch_deadline_s
    try:
        redraw = run_loop(
            photo, width, height, page_w, page_h,
            max_rounds=settings.sketch_max_rounds,
            ask=lambda a: ask(a, settings),
            render=lambda shapes: render_png(shapes, page_w, page_h, width, height, photo),
            words=words,
            time_left=lambda: now() < deadline,
            ink=ink_box(photo),
        )  # fmt: skip
        return _store(db, ids, version, token, redraw)
    except BaseException:
        _release(db, ids[1], token)
        raise


def stale_after(settings: Settings) -> float:
    """The longest a run can take: its deadline, then one more call with its retries."""
    return settings.sketch_deadline_s + 3 * settings.sketch_timeout_s


def _store(
    db: Session, ids: tuple[uuid.UUID, uuid.UUID], version: int, token: str, redraw: Redraw
) -> tuple[dict[str, Any], Page]:
    doc_id, page_id = ids
    page = _locked(db, page_id)
    doc = db.get(Document, doc_id, populate_existing=True)
    claim = page.meta.get(RUN_KEY) if page else None
    mine = isinstance(claim, dict) and claim.get("token") == token
    if page is None or doc is None or doc.version != version or not mine:
        raise AppError(
            "redraw_superseded",
            "The drawing changed while it was being redrawn. Try again.",
            409,
        )
    # Earlier redraws of this page, and a gap-filling pass from before, are replaced.
    db.execute(
        delete(Element).where(
            Element.page_id == page.id, Element.source.in_((SKETCH_SOURCE, UPSCALE_SOURCE))
        )
    )
    db.add_all([_row(doc_id, page_id, s) for s in redraw.shapes])
    entry = sketch_cache_entry(
        version,
        redraw.model,
        len(redraw.shapes),
        rounds=redraw.rounds,
        matched=redraw.matched,
        input_tokens=redraw.input_tokens,
        output_tokens=redraw.output_tokens,
    )
    page.meta = {**{k: v for k, v in page.meta.items() if k != RUN_KEY}, "upscale": entry}
    # Answers cached before now did not know these elements (see qa/service.py).
    doc.meta = {**doc.meta, "upscales": int(doc.meta.get("upscales", 0)) + 1}
    db.flush()
    log.info("sketch: page %s redrawn in %d rounds (matched: %s)",
             page_id, redraw.rounds, redraw.matched)  # fmt: skip
    return _result(entry, cached=False), page


def _release(db: Session, page_id: uuid.UUID, token: str) -> None:
    """Drop our claim after a failure. Never raises: the original error matters more."""
    try:
        db.rollback()
        page = _locked(db, page_id)
        claim = page.meta.get(RUN_KEY) if page else None
        if page is not None and isinstance(claim, dict) and claim.get("token") == token:
            page.meta = {k: v for k, v in page.meta.items() if k != RUN_KEY}
            db.commit()
    except Exception:
        log.exception("sketch: could not release the claim on page %s", page_id)
        db.rollback()


def _locked(db: Session, page_id: uuid.UUID) -> Page | None:
    return db.scalar(
        select(Page)
        .where(Page.id == page_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _words(db: Session, page: Page) -> list[Word]:
    """What ingest read on the page: only to confirm numbers the model wrote."""
    rows = db.scalars(
        select(Element).where(
            Element.page_id == page.id,
            Element.source.not_in((SKETCH_SOURCE, UPSCALE_SOURCE)),
            Element.text.is_not(None),
        )
    ).all()
    return [
        Word(str(el.text), (el.bbox[0], el.bbox[1], el.bbox[2], el.bbox[3]))
        for el in rows
        if el.bbox and len(el.bbox) == 4
    ]


def _row(doc_id: uuid.UUID, page_id: uuid.UUID, shape: Shape) -> Element:
    named = shape.kind in ("room", "text")
    return Element(
        document_id=doc_id,
        page_id=page_id,
        kind=shape.kind,
        text=shape.text,
        label=clip(shape.text, LABEL_MAX) if named else None,
        name=clip(shape.text, NAME_MAX) if shape.kind == "room" else None,
        bbox=list(shape.bbox),
        properties=shape.properties,
        source=SKETCH_SOURCE,
        confidence=SKETCH_CONFIDENCE,
    )


def _result(entry: dict[str, Any], cached: bool) -> dict[str, Any]:
    return {
        "added": int(entry.get("added", 0)),
        "cached": cached,
        "mode": SKETCH_MODE,
        "rounds": int(entry.get("rounds", 0)),
    }
