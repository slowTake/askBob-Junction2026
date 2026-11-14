"""POST /api/documents/{id}/pages/{index}/upscale on a raster image: the sketch redraw.

In-memory SQLite, a temporary data directory and a scripted fake model, so nothing
leaves the process. The page is 2000 x 1000 px and the test limits the image sent to
1000 px on its longer side, so the model sees it at half size (scale 0.5).
"""

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
from app.upscale.sketch_model import SketchAsk
from app.upscale.vision import Look, VisionError

PAGE_W, PAGE_H = 2000, 1000
NOW = 1_000_000.0  # the fake clock, in seconds


def _plan(matches: bool = False, **extra: Any) -> dict[str, Any]:
    return {
        "matches": matches,
        "walls": [{"x0": 100, "y0": 100, "x1": 900, "y1": 100, "outer": True}],
        "doors": [], "windows": [],
        "rooms": [{"name": "bedroom", "x": 300, "y": 300, "outline": []}],
        "texts": [],
        **extra,
    }  # fmt: skip


class Harness:
    def __init__(self, client: TestClient, sessions: sessionmaker[Session]) -> None:
        self.client = client
        self.sessions = sessions
        self.answers: list[object] = []
        self.asks: list[SketchAsk] = []
        self.during: Any = None  # run inside the first model call
        self.doc_id = uuid.uuid4()

    def ask(self, ask: SketchAsk, settings: Settings) -> Look:
        self.asks.append(ask)
        if self.during:
            self.during()
        answer = self.answers.pop(0)
        if isinstance(answer, VisionError):
            raise answer
        return Look(answer, "fake-opus", 6000, 2500)

    def post(self) -> dict[str, Any]:
        response = self.client.post(f"/api/documents/{self.doc_id}/pages/0/upscale")
        return {"status": response.status_code, **response.json()}

    def elements(self) -> list[Element]:
        with self.sessions() as db:
            return list(db.scalars(select(Element).order_by(Element.source, Element.kind)).all())

    def page(self) -> Page:
        with self.sessions() as db:
            return db.scalars(select(Page)).one()

    def set_meta(self, **meta: Any) -> None:
        with self.sessions() as db:
            page = db.scalars(select(Page)).one()
            page.meta = {**page.meta, **meta}
            db.commit()

    def seed(self) -> None:
        with self.sessions() as db:
            doc = Document(id=self.doc_id, filename="napkin.webp", kind="image", status="ready",
                           sha256="0" * 64, size_bytes=1, page_count=1, version=2,
                           meta={"extension": ".webp"})  # fmt: skip
            page = Page(document_id=self.doc_id, index=0, width_px=PAGE_W, height_px=PAGE_H,
                        dpi=96, mm_per_px=0.26, meta={"words": 3})  # fmt: skip
            db.add_all([doc, page])
            db.flush()
            # What ingest read: OCR text and a door from the floor-plan model.
            db.add_all([
                Element(document_id=self.doc_id, page_id=page.id, kind="text", source="ocr",
                        text="bedr00m", bbox=[500, 550, 700, 600], properties={},
                        confidence=0.4),
                Element(document_id=self.doc_id, page_id=page.id, kind="door", source="vision",
                        bbox=[100, 100, 180, 180], properties={}, confidence=0.7),
                Element(document_id=self.doc_id, page_id=page.id, kind="wall", source="upscale",
                        bbox=[0, 0, 10, 10], properties={}, confidence=0.5),
            ])  # fmt: skip
            db.commit()
        path = page_image_path(self.doc_id, 0)
        path.parent.mkdir(parents=True)
        Image.new("RGB", (PAGE_W, PAGE_H), "white").save(path)


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("VALKEY_URL", "redis://unused")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SKETCH_MAX_SIDE", "1000")
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
    monkeypatch.setattr(upscale, "ask_sketch", h.ask)
    monkeypatch.setattr(upscale, "find_missing", lambda *a: pytest.fail("not a sketch pass"))
    monkeypatch.setattr(upscale, "clock", lambda: NOW)
    yield h
    get_settings.cache_clear()


def test_the_model_draws_the_whole_page_and_checks_it(harness: Harness) -> None:
    harness.seed()
    harness.answers = [_plan(), _plan(matches=True)]
    body = harness.post()

    assert body["status"] == 200 and body["ok"] is True
    # One wall and one room; two rounds (a draft and a check that matched).
    assert body["data"] == {
        "added": 2, "cached": False, "mode": "sketch", "rounds": 2, "page": body["data"]["page"],
    }  # fmt: skip
    assert body["data"]["page"]["upscale"] == {
        "added": 2, "model": "fake-opus", "mode": "sketch", "rounds": 2,
    }  # fmt: skip
    first, check = harness.asks
    assert (first.width, first.height) == (1000, 500)  # 2000 x 1000 at half size
    assert check.draft_png is not None and check.draft_png.startswith(b"\x89PNG")

    sketch = [e for e in harness.elements() if e.source == "sketch"]
    room, wall = sorted(sketch, key=lambda e: e.kind)
    # Image (100, 100)-(900, 100) doubled to page (200, 200)-(1800, 200). Outer walls are
    # 1.2 % of 2000 = 24 px thick: the band is 188..1812 by 188..212.
    assert wall.bbox == [188, 188, 1812, 212] and wall.confidence == 0.8
    assert wall.properties["segment_px"] == [[200, 200], [1800, 200]]
    assert (room.name, room.label, room.text) == ("bedroom", "bedroom", "bedroom")
    assert room.properties["label_px"] == [600, 600]
    assert "area_m2" not in room.properties and room.value_mm is None


def test_ingest_elements_stay_and_an_earlier_gap_filling_pass_is_replaced(
    harness: Harness,
) -> None:
    harness.seed()
    harness.answers = [_plan(), _plan(matches=True)]
    harness.post()
    sources = sorted(e.source for e in harness.elements())
    assert sources == ["ocr", "sketch", "sketch", "vision"]  # the "upscale" wall is gone


def test_a_second_click_is_served_from_the_cache(harness: Harness) -> None:
    harness.seed()
    harness.answers = [_plan(), _plan(matches=True)]
    harness.post()
    again = harness.post()
    assert again["data"]["cached"] is True and again["data"]["added"] == 2
    assert len(harness.asks) == 2  # no new model call


def test_a_click_while_a_redraw_runs_is_refused_at_once(harness: Harness) -> None:
    harness.seed()
    harness.set_meta(sketch_run={"token": "other", "started_s": NOW - 60})
    body = harness.post()
    assert body["status"] == 409 and body["error"]["code"] == "redraw_running"
    assert harness.asks == []
    assert harness.page().meta["sketch_run"]["token"] == "other"  # their claim stands


def test_a_claim_left_by_a_dead_run_goes_stale(harness: Harness) -> None:
    harness.seed()
    # Deadline 600 s plus three calls of 300 s: stale after 1500 s.
    harness.set_meta(sketch_run={"token": "dead", "started_s": NOW - 1500})
    harness.answers = [_plan(), _plan(matches=True)]
    assert harness.post()["status"] == 200
    assert "sketch_run" not in harness.page().meta  # our own claim is dropped when done


def test_while_the_model_works_the_page_is_claimed_and_no_lock_is_held(
    harness: Harness,
) -> None:
    harness.seed()
    seen: list[object] = []
    # Reading and writing the page from another session during the call works, and
    # sees our claim.
    harness.during = lambda: seen.append(harness.page().meta.get("sketch_run"))
    harness.answers = [_plan(), _plan(matches=True)]
    harness.post()
    claim = seen[0]
    assert isinstance(claim, dict) and claim["started_s"] == NOW


@pytest.mark.parametrize(
    ("error", "status", "code", "message"),
    [
        (VisionError("llm_busy"), 503, "llm_busy",
         "The language model is busy. Try again in a minute."),
        (VisionError("sketch_needs_claude"), 503, "sketch_needs_claude",
         "Redrawing a sketch needs the Claude model, and the server is set to another one."),
        (VisionError("sketch_unreadable"), 422, "sketch_unreadable",
         "No floor plan could be read from this image."),
        (VisionError("sketch_failed"), 502, "sketch_failed",
         "The sketch could not be redrawn. Try again."),
    ],
)  # fmt: skip
def test_a_failed_redraw_stores_nothing_and_frees_the_page(
    harness: Harness, error: VisionError, status: int, code: str, message: str
) -> None:
    harness.seed()
    harness.answers = [error]
    body = harness.post()

    assert body == {
        "status": status, "ok": False, "data": None, "error": {"code": code, "message": message},
    }  # fmt: skip
    assert "sketch" not in [e.source for e in harness.elements()]
    meta = harness.page().meta
    assert "sketch_run" not in meta and "upscale" not in meta
    harness.answers = [_plan(), _plan(matches=True)]
    assert harness.post()["data"]["cached"] is False  # a failure is not cached


def test_a_document_reprocessed_during_the_redraw_is_not_overwritten(harness: Harness) -> None:
    harness.seed()

    def reprocess() -> None:
        harness.during = None
        with harness.sessions() as db:
            db.get_one(Document, harness.doc_id).version = 3
            db.commit()

    harness.during = reprocess
    harness.answers = [_plan(), _plan(matches=True)]
    body = harness.post()

    assert body["status"] == 409 and body["error"]["code"] == "redraw_superseded"
    assert "sketch" not in [e.source for e in harness.elements()]
    assert "sketch_run" not in harness.page().meta
