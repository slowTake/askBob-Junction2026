import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.ingest import companions
from app.ingest.types import ExtractedDocument
from app.models import Base, Document
from app.valkey import QueueError


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)

    @contextmanager
    def scope() -> Iterator[Session]:
        with sessions() as db:
            yield db
            db.commit()

    monkeypatch.setattr(companions, "session_scope", scope)
    monkeypatch.setattr(companions, "publish_event", lambda *_: None)
    monkeypatch.setattr(companions, "get_settings", lambda: Settings.model_construct())
    monkeypatch.setattr(companions, "original_path", lambda *_: Path("/unused/floor.dxf"))
    yield sessions
    engine.dispose()


def _add(
    store: sessionmaker[Session],
    kind: str,
    status: str = "ready",
    name: str = "floor",
    digest: str = "same",
) -> uuid.UUID:
    with store() as db:
        doc = Document(
            filename=f"{name}.{'png' if kind == 'image' else 'dxf'}",
            kind=kind,
            status=status,
            sha256=digest,
            size_bytes=100,
            meta={},
        )
        db.add(doc)
        db.commit()
        return doc.id


def test_image_first_refreshes_only_its_matching_drawing(
    store: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    image = _add(store, "image")
    other = _add(store, "image", name="other-floor")
    cad = _add(store, "dxf")
    queued: list[str] = []
    monkeypatch.setattr(companions, "enqueue_ingest", queued.append)
    companions.refresh_companion_images(cad)
    assert queued == [str(image)]
    with store() as db:
        assert db.get_one(Document, image).status == "queued"
        assert db.get_one(Document, other).status == "ready"


def test_dxf_first_or_arriving_during_processing_is_checked_on_image_completion(
    store: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    cad = _add(store, "dxf")
    image = _add(store, "image", status="processing")
    queued: list[str] = []
    monkeypatch.setattr(companions, "enqueue_ingest", queued.append)
    companions.refresh_companion_images(cad)
    assert queued == []
    with store() as db:
        db.get_one(Document, image).status = "ready"
        db.commit()
    companions.refresh_companion_images(image)
    assert queued == [str(image)]


def test_a_failed_alignment_is_attempted_once_per_companion_hash(
    store: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    cad = _add(store, "dxf")
    image = _add(store, "image")
    with store() as db:
        db.get_one(Document, image).meta = {"companion_attempt": {"sha256": "same"}}
        db.commit()
    queued: list[str] = []
    monkeypatch.setattr(companions, "enqueue_ingest", queued.append)
    companions.refresh_companion_images(cad)
    assert queued == []


def test_ambiguous_revisions_are_not_used(
    store: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    image = _add(store, "image")
    cad = _add(store, "dxf")
    _add(store, "dxf", digest="different-revision")
    queued: list[str] = []
    monkeypatch.setattr(companions, "enqueue_ingest", queued.append)
    assert companions.load_companion(image) is None
    companions.refresh_companion_images(cad)
    assert queued == []


def test_queue_failure_keeps_the_existing_image_ready(
    store: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    image = _add(store, "image")
    cad = _add(store, "dxf")

    def fail(*_: Any) -> None:
        raise QueueError()

    monkeypatch.setattr(companions, "enqueue_ingest", fail)
    companions.refresh_companion_images(cad)
    with store() as db:
        assert db.get_one(Document, image).status == "ready"


def test_companion_read_failure_still_records_which_file_was_attempted(
    store: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    image = _add(store, "image")
    cad = _add(store, "dxf")

    def fail(*_: Any) -> ExtractedDocument:
        raise ValueError("unreadable drawing")

    monkeypatch.setattr(companions, "read_dxf", fail)
    loaded = companions.load_companion(image)
    assert loaded is not None and loaded.data is None
    assert loaded.info["document_id"] == str(cad)
    assert companions.load_companion(cad) is None
    assert companions.load_companion(uuid.uuid4()) is None


def test_successfully_loads_the_uploaded_native_drawing(
    store: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    image = _add(store, "image")
    _add(store, "dxf")
    native = ExtractedDocument()
    monkeypatch.setattr(companions, "read_dxf", lambda *_: native)
    loaded = companions.load_companion(image)
    assert loaded is not None and loaded.data is native
