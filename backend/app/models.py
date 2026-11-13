"""The canonical building model. Every fact keeps where it came from.

- Document: one uploaded file (IFC, PDF, image).
- Page: a rendered page of a drawing (IFC files have none).
- Element: one fact-bearing thing: a room label, a wall, a door, a dimension, an IFC
  product. `bbox` (page pixels) or `ifc_guid` is its provenance; `source` and
  `confidence` say how it was extracted.
- QaLog: every question and answer, for evaluation and the Aiven usage log.
"""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JsonDict = JSON().with_variant(JSONB(), "postgresql")
EMBEDDING_DIM = 1024
LABEL_MAX = 256  # ingest clips longer values to fit (app/ingest/persist.py)
NAME_MAX = 512


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(512))
    kind: Mapped[str] = mapped_column(String(16))  # ifc | pdf | image
    status: Mapped[str] = mapped_column(String(16), default="queued")
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    has_model: Mapped[bool] = mapped_column(Boolean, default=False)  # IFC + mesh available
    meta: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)  # bump on re-ingest
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pages: Mapped[list["Page"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Page.index"
    )


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    index: Mapped[int] = mapped_column(Integer)  # 0-based
    width_px: Mapped[int] = mapped_column(Integer)
    height_px: Mapped[int] = mapped_column(Integer)
    dpi: Mapped[float | None] = mapped_column(Float)
    mm_per_px: Mapped[float | None] = mapped_column(Float)  # None until the scale is known
    meta: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)

    document: Mapped[Document] = relationship(back_populates="pages")


class Element(Base):
    __tablename__ = "elements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), index=True)
    text: Mapped[str | None] = mapped_column(Text)  # raw text as found in the source
    label: Mapped[str | None] = mapped_column(String(LABEL_MAX))  # normalized, e.g. "MH", "09"
    name: Mapped[str | None] = mapped_column(String(NAME_MAX))  # human-readable
    value_mm: Mapped[float | None] = mapped_column(Float)
    bbox: Mapped[list[float] | None] = mapped_column(JsonDict)  # [x0, y0, x1, y1] page px
    footprint_mm: Mapped[list[list[float]] | None] = mapped_column(JsonDict)  # plan polygon
    ifc_guid: Mapped[str | None] = mapped_column(String(64), index=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    source: Mapped[str] = mapped_column(String(32))  # ifc | pdf_text | pdf_vector | ocr | derived
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    # TODO(search): embed text-heavy elements (notes, schedules) for semantic search.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))


class QaLog(Base):
    __tablename__ = "qa_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    question: Mapped[str] = mapped_column(Text)
    document_ids: Mapped[list[str]] = mapped_column(JsonDict, default=list)
    answer: Mapped[dict[str, Any] | None] = mapped_column(JsonDict)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    model: Mapped[str] = mapped_column(String(64))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
