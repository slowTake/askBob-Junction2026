"""Upload and reingest when the ingest queue (Valkey) cannot take the job (#9).

The routes run against an in-memory SQLite database and a temporary data directory;
the queue is replaced by a fake, so no Postgres or Valkey is needed.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import documents
from app.config import get_settings
from app.db import get_db
from app.envelope import install_error_handlers
from app.models import Base, Document
from app.valkey import QueueError

PDF = b"%PDF-1.7 minimal"


class Harness:
    def __init__(self, client: TestClient, sessions: sessionmaker[Session], data_dir: Path) -> None:
        self.client = client
        self.sessions = sessions
        self.data_dir = data_dir
        self.enqueued: list[str] = []
        self.queue_up = True

    def enqueue(self, document_id: str) -> None:
        if not self.queue_up:
            raise QueueError("valkey unreachable")
        self.enqueued.append(document_id)

    def documents(self) -> list[Document]:
        with self.sessions() as db:
            return list(db.scalars(select(Document)).all())

    def stored_files(self) -> list[Path]:
        return [p for p in self.data_dir.rglob("*") if p.is_file()]


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("VALKEY_URL", "redis://unused")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)

    def db() -> Iterator[Session]:
        with sessions() as session:
            yield session

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(documents.router)
    app.dependency_overrides[get_db] = db
    h = Harness(TestClient(app, raise_server_exceptions=False), sessions, tmp_path)
    monkeypatch.setattr(documents, "enqueue_ingest", h.enqueue)
    monkeypatch.setattr(documents, "publish_event", lambda event: None)
    yield h
    get_settings.cache_clear()


def _upload(h: Harness) -> dict[str, object]:
    response = h.client.post("/api/documents", files={"file": ("plan.pdf", PDF)})
    return {"status": response.status_code, **response.json()}


def test_upload_queues_the_document_when_the_queue_is_up(harness: Harness) -> None:
    body = _upload(harness)
    assert body["status"] == 200 and body["ok"] is True
    [doc] = harness.documents()
    assert doc.status == "queued"
    assert harness.enqueued == [str(doc.id)]
    assert len(harness.stored_files()) == 1


def test_upload_is_rolled_back_when_the_job_cannot_be_enqueued(harness: Harness) -> None:
    harness.queue_up = False
    body = _upload(harness)
    assert body["status"] == 503
    assert body["ok"] is False and body["data"] is None
    assert body["error"] == {
        "code": "queue_unavailable",
        "message": "Processing is unavailable right now. Try again in a minute.",
    }
    assert harness.documents() == []  # nothing left in "queued" without a job
    assert harness.stored_files() == []


def test_reingest_keeps_the_old_status_when_the_job_cannot_be_enqueued(harness: Harness) -> None:
    _upload(harness)
    [doc] = harness.documents()
    with harness.sessions() as db:
        db.get_one(Document, doc.id).status = "ready"
        db.commit()

    harness.queue_up = False
    response = harness.client.post(f"/api/documents/{doc.id}/reingest")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "queue_unavailable"
    [after] = harness.documents()
    assert after.status == "ready"  # still usable; not stuck in "queued"
