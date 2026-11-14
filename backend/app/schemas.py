"""API shapes. The frontend mirrors these in frontend/src/api/types.ts."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.domain.ingest_errors import error_message


class PageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    index: int
    width_px: int
    height_px: int
    dpi: float | None
    mm_per_px: float | None
    meta: dict[str, Any] = Field(default_factory=dict, exclude=True)

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

        Re-ingest replaces the pages, so a page that carries this is up to date.
        """
        entry = self.meta.get("upscale")
        if not isinstance(entry, dict):
            return None
        return {"added": int(entry.get("added", 0)), "model": str(entry.get("model", ""))}


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
