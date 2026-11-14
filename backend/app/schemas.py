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


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    document_ids: list[uuid.UUID] = Field(default_factory=list)  # empty = all ready documents
