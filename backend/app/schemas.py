"""API shapes. The frontend mirrors these in frontend/src/api/types.ts."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, computed_field

from app.domain.ingest_errors import error_message
from app.domain.redraw_confidence import CONFIDENCE_KEY, confidence_from_meta
from app.domain.redraw_mode import page_redraw_mode
from app.domain.sketch import SKETCH_MODE
from app.domain.upscale import FILL_MODE, UPSCALE_FORMAT


class PageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    index: int
    width_px: int
    height_px: int
    dpi: float | None
    mm_per_px: float | None
    meta: dict[str, Any] = Field(default_factory=dict, exclude=True)
    # From the page row's document; None when built without one (not a raster image).
    document_kind: str | None = Field(
        default=None,
        exclude=True,
        validation_alias=AliasChoices("document_kind", AliasPath("document", "kind")),
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def label(self) -> str | None:
        """What the page shows, when known: the storey of an IFC floor plan."""
        storey = self.meta.get("storey")
        return str(storey) if storey else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def upscale(self) -> dict[str, Any] | None:
        """Set once the page had its vision pass (#82): how many elements it added.

        `mode` is "sketch" for the full redraw of a raster image page (with the number
        of model rounds it took), "fill" for the gap-filling pass on other formats.
        Re-ingest replaces the pages, so only the format can make an entry stale.
        """
        entry = self.meta.get("upscale")
        if not isinstance(entry, dict) or entry.get("format") != UPSCALE_FORMAT:
            return None  # never run, or run under older rules: the server runs it again
        rounds = entry.get("rounds")
        return {
            "added": int(entry.get("added", 0)),
            "model": str(entry.get("model", "")),
            "mode": str(entry.get("mode", FILL_MODE)),
            "rounds": int(rounds) if isinstance(rounds, int) else None,
        }

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redraw_mode(self) -> str:
        """Which redraw the page gets, or got (#138): "plan" (the page redraw) or "sketch".

        Decided from what the page looks like; an upscale with `?mode=` the other way
        changes it to the mode that ran.
        """
        return page_redraw_mode(self.document_kind or "", self.meta)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redraw_confidence(self) -> dict[str, Any] | None:
        """How much of the page's own ink the page redraw accounts for (#132), with its
        parts and the missed and added patches; None when the page was never scored
        (PDF, CAD, older pages) or gets the sketch redraw, which measures nothing."""
        if self.redraw_mode == SKETCH_MODE:
            return None
        return confidence_from_meta(self.meta.get(CONFIDENCE_KEY))


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    kind: str
    status: str
    page_count: int
    has_model: bool
    size_bytes: int
    error_code: str | None
    created_at: datetime
    meta: dict[str, Any]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def error_message(self) -> str | None:
        return error_message(self.error_code)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_ifc(self) -> bool:
        """An IFC model is downloadable: uploaded IFC, or one built from the drawing."""
        return self.status == "ready" and (self.kind == "ifc" or "model" in self.meta)


class DocumentDetailOut(DocumentOut):
    pages: list[PageOut]


class ElementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    page_id: uuid.UUID | None
    kind: str
    text: str | None
    label: str | None
    name: str | None
    value_mm: float | None
    bbox: list[float] | None
    ifc_guid: str | None
    properties: dict[str, Any]
    source: str
    confidence: float


MAX_SELECTED = 20  # elements selected on the plan (Shift+click) that one question can carry


class AskContextIn(BaseModel):
    """What the user looks at while asking, so "this room" and "here" mean something."""

    document_id: uuid.UUID | None = None
    page_index: int | None = Field(default=None, ge=0)
    element_id: uuid.UUID | None = None  # one element clicked on the plan (older clients)
    element_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_SELECTED)

    def selected_ids(self) -> list[uuid.UUID]:
        """Every selected element once, in click order; `element_id` comes last."""
        ids = [*self.element_ids, *([self.element_id] if self.element_id else [])]
        return list(dict.fromkeys(ids))


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    document_ids: list[uuid.UUID] = Field(default_factory=list)  # empty = all ready documents
    context: AskContextIn | None = None
