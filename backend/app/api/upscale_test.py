"""POST /api/documents/{id}/pages/{index}/upscale with a fake vision call (#82).

In-memory SQLite and a temporary data directory, like documents_test.py. The model
is replaced by a function that returns a canned answer, so nothing leaves the process.
"""

import io
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import upscale
from app.config import Settings, get_settings
from app.db import get_db
from app.envelope import install_error_handlers
from app.models import Base, Document, Element, Page
from app.storage import page_image_path
from app.upscale.vision import Look, VisionError

PAGE_W, PAGE_H = 2000, 1000  # sent at 1000 x 500: the test limits the image side to 1000


class Harness:
    def __init__(self, client: TestClient, sessions: sessionmaker[Session]) -> None:
        self.client = client
        self.sessions = sessions
        self.answer: Any = {"elements": []}
        self.error: VisionError | None = None
        self.calls: list[dict[str, Any]] = []
        self.doc_id = uuid.uuid4()

    def look(
        self,
        image_png: bytes,
        width: int,
        height: int,
        listed: list[dict[str, object]],
        omitted: int,
        settings: Settings,
    ) -> Look:
        with Image.open(io.BytesIO(image_png)) as image:
            sent = image.size
        self.calls.append({"size": (width, height), "sent": sent, "listed": listed})
        if self.error:
            raise self.error
        return Look(self.answer, "fake-vision", 3000, 400)

    def post(self, index: int = 0) -> dict[str, Any]:
        response = self.client.post(f"/api/documents/{self.doc_id}/pages/{index}/upscale")
        return {"status": response.status_code, **response.json()}

    def elements(self) -> list[Element]:
        with self.sessions() as db:
            return list(db.scalars(select(Element).order_by(Element.kind)).all())

    def seed(self, status: str = "ready", image: bool = True) -> None:
        with self.sessions() as db:
            # A PDF: raster images get the sketch redraw instead (sketch_test.py).
            doc = Document(id=self.doc_id, filename="plan.pdf", kind="pdf", status=status,
                           sha256="0" * 64, size_bytes=1, page_count=1, version=2,
                           meta={"extension": ".pdf"})  # fmt: skip
            page = Page(document_id=self.doc_id, index=0, width_px=PAGE_W, height_px=PAGE_H,
                        dpi=150, mm_per_px=None, meta={"words": 3})  # fmt: skip
            db.add_all([doc, page])
            db.flush()
            db.add(Element(document_id=self.doc_id, page_id=page.id, kind="door", source="derived",
                           bbox=[100, 100, 180, 180], properties={}, confidence=0.6))  # fmt: skip
            db.commit()
        if image:
            path = page_image_path(self.doc_id, 0)
            path.parent.mkdir(parents=True)
            Image.new("RGB", (PAGE_W, PAGE_H), "white").save(path)


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("VALKEY_URL", "redis://unused")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("UPSCALE_MAX_SIDE", "1000")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)

    def db() -> Iterator[Session]:
        with sessions() as session:
            yield session
            session.commit()

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(upscale.router)
    app.dependency_overrides[get_db] = db
    h = Harness(TestClient(app, raise_server_exceptions=False), sessions)
    monkeypatch.setattr(upscale, "find_missing", h.look)
    yield h
    get_settings.cache_clear()


def _found(kind: str, box: tuple[float, float, float, float], **over: Any) -> dict[str, Any]:
    x0, y0, x1, y1 = box
    return {
        "kind": kind, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "label": None, "confidence": 0.8,
        **over,
    }  # fmt: skip


def test_adds_what_the_model_found_in_page_pixels(harness: Harness) -> None:
    harness.seed()
    harness.answer = {
        "elements": [
            _found("wall", (100, 400, 600, 410), confidence=0.7),
            _found("room", (100, 200, 300, 400), label="Küche", confidence=0.95),
            _found("door", (55, 55, 85, 85)),  # the door ingest already has
        ]
    }
    body = harness.post()

    assert body["status"] == 200 and body["ok"] is True
    assert body["data"]["added"] == 2 and body["data"]["cached"] is False
    assert body["data"]["page"]["upscale"] == {
        "added": 2, "model": "fake-vision", "mode": "fill", "rounds": None,
    }  # fmt: skip
    [call] = harness.calls
    # 2000 x 1000 with the longest side limited to 1000: half size.
    assert call["size"] == (1000, 500) and call["sent"] == (1000, 500)
    # The known door (100, 100, 180, 180), halved.
    assert call["listed"] == [{"kind": "door", "box": [50, 50, 90, 90]}]

    door, room, wall = harness.elements()
    assert (door.source, door.bbox) == ("derived", [100, 100, 180, 180])  # untouched
    # Image pixels doubled back to page pixels.
    assert (wall.source, wall.bbox, wall.confidence) == ("upscale", [200, 800, 1200, 820], 0.7)
    assert (room.source, room.bbox, room.confidence) == ("upscale", [200, 400, 600, 800], 0.9)
    assert (room.text, room.label, room.name) == ("Küche", "Küche", "Küche")
    # The room's outline is its box, marked as approximate; no area is made up.
    assert room.properties == {
        "polygon_px": [[200, 400], [600, 400], [600, 800], [200, 800]],
        "outline": "approximate",
    }


def test_a_second_click_costs_nothing(harness: Harness) -> None:
    harness.seed()
    harness.answer = {"elements": [_found("wall", (100, 400, 600, 410))]}
    harness.post()
    again = harness.post()

    assert again["data"]["cached"] is True and again["data"]["added"] == 1
    assert len(harness.calls) == 1  # the model was asked once
    assert [e.source for e in harness.elements()] == ["derived", "upscale"]


def test_a_new_document_version_runs_again_and_replaces_the_additions(harness: Harness) -> None:
    harness.seed()
    harness.answer = {"elements": [_found("wall", (100, 400, 600, 410))]}
    harness.post()
    with harness.sessions() as db:
        db.get_one(Document, harness.doc_id).version = 3
        db.commit()
    harness.answer = {"elements": [_found("window", (700, 100, 760, 110))]}
    body = harness.post()

    assert body["data"]["cached"] is False
    assert len(harness.calls) == 2
    assert [(e.kind, e.source) for e in harness.elements()] == [
        ("door", "derived"),
        ("window", "upscale"),  # the earlier wall is gone, not doubled
    ]


def test_answers_cached_before_the_upscale_are_not_served_after_it(harness: Harness) -> None:
    harness.seed()
    harness.post()
    with harness.sessions() as db:
        doc = db.get_one(Document, harness.doc_id)
        page = db.scalars(select(Page)).one()
    assert doc.meta["upscales"] == 1  # part of the answer-cache key (qa/service.py)
    assert doc.meta["extension"] == ".pdf" and doc.version == 2
    assert page.meta["words"] == 3  # the reader's page meta is kept
    assert page.meta["upscale"]["document_version"] == 2


@pytest.mark.parametrize(
    ("code", "status", "message"),
    [
        ("llm_not_configured", 503, "The language model is not configured on the server."),
        ("llm_busy", 503, "The language model is busy. Try again in a minute."),
        ("upscale_failed", 502, "The page could not be upscaled. Try again."),
    ],
)
def test_a_failed_vision_call_changes_nothing(
    harness: Harness, code: str, status: int, message: str
) -> None:
    harness.seed()
    harness.error = VisionError(code)
    body = harness.post()

    assert body["status"] == status
    assert body == {
        "status": status, "ok": False, "data": None, "error": {"code": code, "message": message},
    }  # fmt: skip
    assert [e.source for e in harness.elements()] == ["derived"]
    harness.error = None
    assert harness.post()["data"]["cached"] is False  # a failure is not cached


def test_an_answer_without_an_element_list_is_a_failed_upscale(harness: Harness) -> None:
    harness.seed()
    harness.answer = {"walls": []}
    body = harness.post()
    assert body["status"] == 502 and body["error"]["code"] == "upscale_failed"


def test_unknown_document_page_or_image_is_not_found(harness: Harness) -> None:
    assert harness.post()["status"] == 404
    harness.seed(image=False)
    assert harness.post(index=5)["error"]["code"] == "not_found"
    assert harness.post()["error"]["code"] == "not_found"  # the page image is missing
    assert harness.calls == []


def test_a_document_still_being_read_cannot_be_upscaled(harness: Harness) -> None:
    harness.seed(status="processing")
    body = harness.post()
    assert body["status"] == 409 and body["error"]["code"] == "not_ready"
    assert harness.calls == []
