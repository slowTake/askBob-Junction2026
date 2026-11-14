"""Upscale one page (#82): resize its image, ask the model once, store what it adds.

The decisions (what counts, what is a duplicate, when a page is done) are the pure
functions in `app/domain/upscale.py`; this file only moves data between the page
image, the model and Postgres.
"""

import io
from collections.abc import Callable
from typing import Any

from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.extent import element_extent
from app.domain.text import clip
from app.domain.upscale import (
    ADDABLE_KINDS,
    UPSCALE_SOURCE,
    Candidate,
    Known,
    cache_entry,
    image_scale,
    is_cached,
    listed_elements,
    merge_candidates,
    parse_candidates,
)
from app.envelope import AppError
from app.models import LABEL_MAX, NAME_MAX, Document, Element, Page
from app.storage import page_image_path
from app.upscale.vision import Look, VisionError

Looker = Callable[[bytes, int, int, list[dict[str, object]], int, Settings], Look]


def upscale_page(
    db: Session, doc: Document, page: Page, settings: Settings, look: Looker
) -> dict[str, Any]:
    """Run the vision pass unless this page already had it for this document version.

    Raises VisionError when the model call fails or its answer is unusable; nothing
    is stored then, so the next click tries again.
    """
    if is_cached(page.meta, doc.version):
        return {"added": int(page.meta["upscale"]["added"]), "cached": True}
    path = page_image_path(doc.id, page.index)
    if not path.is_file():
        raise AppError("not_found", "File not available", 404)

    scale = image_scale(page.width_px, page.height_px, settings.upscale_max_side)
    width = max(1, round(page.width_px * scale))
    height = max(1, round(page.height_px * scale))
    with Image.open(path) as image:
        buffer = io.BytesIO()
        image.convert("RGB").resize((width, height)).save(buffer, format="PNG")

    known = _known(db, page)
    listed = listed_elements(known, scale)
    listable = sum(1 for k in known if k.kind in ADDABLE_KINDS)
    seen = look(buffer.getvalue(), width, height, listed, listable - len(listed), settings)
    try:
        candidates = parse_candidates(seen.data, scale, page.width_px, page.height_px)
    except ValueError:
        raise VisionError("upscale_failed") from None
    added = merge_candidates(known, candidates)

    # A page that ran before (older document version or format) starts over.
    db.execute(delete(Element).where(Element.page_id == page.id, Element.source == UPSCALE_SOURCE))
    db.add_all([_row(doc, page, c) for c in added])
    page.meta = {
        **page.meta,
        "upscale": cache_entry(
            doc.version, seen.model, len(added), seen.input_tokens, seen.output_tokens
        ),
    }
    # Answers cached before now did not know these elements (see qa/service.py).
    doc.meta = {**doc.meta, "upscales": int(doc.meta.get("upscales", 0)) + 1}
    db.flush()
    return {"added": len(added), "cached": False}


def _known(db: Session, page: Page) -> list[Known]:
    rows = db.scalars(
        select(Element).where(Element.page_id == page.id, Element.source != UPSCALE_SOURCE)
    ).all()
    known: list[Known] = []
    for el in rows:
        box = (el.bbox[0], el.bbox[1], el.bbox[2], el.bbox[3]) if el.bbox else None
        extent = element_extent(el.kind, box, el.properties).bbox
        if extent is not None:
            known.append(Known(el.kind, extent, el.label or el.text))
    return known


def _row(doc: Document, page: Page, c: Candidate) -> Element:
    x0, y0, x1, y1 = c.bbox
    properties: dict[str, Any] = {}
    if c.kind == "room":
        # The outline is the model's box, not traced walls: no area is derived from it.
        properties = {
            "polygon_px": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
            "outline": "approximate",
        }
    return Element(
        document_id=doc.id,
        page_id=page.id,
        kind=c.kind,
        text=c.label,
        label=clip(c.label, LABEL_MAX),
        name=clip(c.label, NAME_MAX) if c.kind == "room" else None,
        bbox=list(c.bbox),
        properties=properties,
        source=UPSCALE_SOURCE,
        confidence=c.confidence,
    )
