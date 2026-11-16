"""Which redraw POST …/upscale runs on a raster image page, and `?mode=` (#138).

In-memory SQLite, a temporary data directory and two fakes: the gap-filling vision pass
(`find_missing`, Haiku in production) and the sketch model (`ask_sketch`, Opus). Nothing
leaves the process. The page is 2000 x 1000 px; both passes are limited to 1000 px on
the longer side, so each model sees it at half size.
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
from app.upscale.sketch_model import SketchAsk
from app.upscale.vision import Look

PAGE_W, PAGE_H = 2000, 1000
# page.meta["page_stats"] as ingest stores them (app/domain/redraw_mode.py):
PRINTED = {"straight_share": 0.472, "fill_share": 0.574, "dimension_words": 9,
           "paper_spread": 0.0}  # fmt: skip  # colorful-34: a plan
NAPKIN = {"straight_share": 0.117, "fill_share": 0.0, "dimension_words": 0,
          "paper_spread": 35.8}  # fmt: skip  # a photographed hand sketch


class Harness:
    def __init__(self, client: TestClient, sessions: sessionmaker[Session]) -> None:
        self.client = client
        self.sessions = sessions
        self.looks: list[dict[str, Any]] = []  # calls to the gap-filling pass
        self.asks: list[SketchAsk] = []  # calls to the sketch model
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
        self.looks.append({"size": (width, height), "sent": sent, "listed": listed})
        found = {"kind": "wall", "x0": 100, "y0": 400, "x1": 600, "y1": 410, "label": None,
                 "confidence": 0.7}  # fmt: skip
        return Look({"elements": [found]}, "fake-haiku", 3000, 400)

    def ask(self, ask: SketchAsk, settings: Settings) -> Look:
        self.asks.append(ask)
        plan = {
            "matches": len(self.asks) > 1,
            "walls": [{"x0": 100, "y0": 100, "x1": 900, "y1": 100, "outer": True}],
            "doors": [], "windows": [], "rooms": [], "texts": [],
        }  # fmt: skip
        return Look(plan, "fake-opus", 6000, 2500)

    def post(self, query: str = "") -> dict[str, Any]:
        response = self.client.post(f"/api/documents/{self.doc_id}/pages/0/upscale{query}")
        return {"status": response.status_code, **response.json()}

    def sources(self) -> list[tuple[str, str]]:
        with self.sessions() as db:
            rows = db.scalars(select(Element).order_by(Element.source, Element.kind)).all()
            return [(e.source, e.kind) for e in rows]

    def seed(self, meta: dict[str, Any], kind: str = "image") -> None:
        with self.sessions() as db:
            doc = Document(id=self.doc_id, filename="plan.png", kind=kind, status="ready",
                           sha256="0" * 64, size_bytes=1, page_count=1, version=2,
                           meta={"extension": ".png"})  # fmt: skip
            page = Page(document_id=self.doc_id, index=0, width_px=PAGE_W, height_px=PAGE_H,
                        dpi=None, mm_per_px=10.0, meta=meta)  # fmt: skip
            db.add_all([doc, page])
            db.flush()
            # What ingest read on the image: an OCR dimension and a door.
            db.add_all([
                Element(document_id=self.doc_id, page_id=page.id, kind="dimension",
                        source="ocr", text="3,450", bbox=[500, 550, 700, 600], properties={},
                        confidence=0.9),
                Element(document_id=self.doc_id, page_id=page.id, kind="door", source="vision",
                        bbox=[100, 100, 180, 180], properties={}, confidence=0.7),
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
    monkeypatch.setenv("UPSCALE_MAX_SIDE", "1000")
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
    monkeypatch.setattr(upscale, "find_missing", h.look)
    monkeypatch.setattr(upscale, "ask_sketch", h.ask)
    monkeypatch.setattr(upscale, "clock", lambda: 1_000_000.0)
    yield h
    get_settings.cache_clear()


def test_a_printed_plan_image_gets_the_page_redraw_like_a_scanned_pdf(harness: Harness) -> None:
    harness.seed({"page_stats": PRINTED})
    body = harness.post()

    assert body["status"] == 200 and body["data"]["added"] == 1
    page = body["data"]["page"]
    assert page["redraw_mode"] == "plan"
    assert page["upscale"] == {"added": 1, "model": "fake-haiku", "mode": "fill", "rounds": None}
    assert harness.asks == []  # no sketch model call
    [look] = harness.looks
    # 2000 x 1000 limited to 1000 px: half size, as on a PDF page (upscale_test.py).
    assert look["size"] == (1000, 500) and look["sent"] == (1000, 500)
    # The door ingest found is listed, halved: (100, 100, 180, 180) -> (50, 50, 90, 90).
    assert look["listed"] == [{"kind": "door", "box": [50, 50, 90, 90]}]
    # Ingest's elements stay, the dimension among them; the pass adds its wall.
    assert harness.sources() == [("ocr", "dimension"), ("upscale", "wall"), ("vision", "door")]


def test_a_photographed_sketch_gets_the_sketch_redraw(harness: Harness) -> None:
    harness.seed({"page_stats": NAPKIN})
    body = harness.post()

    assert body["status"] == 200 and body["data"]["mode"] == "sketch"
    assert body["data"]["page"]["redraw_mode"] == "sketch"
    assert harness.looks == [] and len(harness.asks) == 2  # a draft and a matching check
    assert ("sketch", "wall") in harness.sources()


def test_an_image_ingested_before_page_statistics_is_still_a_sketch(harness: Harness) -> None:
    harness.seed({"words": 3})
    body = harness.post()
    assert body["data"]["mode"] == "sketch" and harness.looks == []


def test_mode_overrides_what_the_page_looks_like(harness: Harness) -> None:
    harness.seed({"page_stats": NAPKIN})
    body = harness.post("?mode=plan")

    assert body["status"] == 200 and body["data"]["page"]["redraw_mode"] == "plan"
    assert len(harness.looks) == 1 and harness.asks == []
    # The page now says plan, so a click without the override serves the cached pass.
    again = harness.post()
    assert again["data"]["cached"] is True and len(harness.looks) == 1


def test_switching_mode_replaces_the_other_redraw(harness: Harness) -> None:
    harness.seed({"page_stats": PRINTED})
    harness.post("?mode=sketch")
    assert ("sketch", "wall") in harness.sources()

    body = harness.post("?mode=plan")
    assert body["data"]["cached"] is False and body["data"]["page"]["redraw_mode"] == "plan"
    # The model is told only what ingest found, not the sketch redraw's wall.
    assert harness.looks[0]["listed"] == [{"kind": "door", "box": [50, 50, 90, 90]}]
    assert harness.sources() == [("ocr", "dimension"), ("upscale", "wall"), ("vision", "door")]

    back = harness.post("?mode=sketch")
    assert back["data"]["mode"] == "sketch" and back["data"]["page"]["redraw_mode"] == "sketch"
    assert ("upscale", "wall") not in harness.sources()


def test_an_unknown_mode_is_refused_in_the_usual_shape(harness: Harness) -> None:
    harness.seed({"page_stats": PRINTED})
    body = harness.post("?mode=photo")
    assert body == {
        "status": 422, "ok": False, "data": None,
        "error": {"code": "validation_error", "message": "The request is not valid"},
    }  # fmt: skip
    assert harness.looks == [] and harness.asks == []


def test_matched_cad_rooms_ignore_the_override(harness: Harness) -> None:
    # D-030: the CAD geometry is the clean plan; no model is asked whatever the mode.
    harness.seed({"page_stats": NAPKIN, "companion_dxf": {"rooms": 1}})
    body = harness.post("?mode=sketch")
    assert body["data"] == {"added": 0, "cached": True, "page": body["data"]["page"]}
    assert body["data"]["page"]["redraw_mode"] == "plan"
    assert harness.looks == [] and harness.asks == []
