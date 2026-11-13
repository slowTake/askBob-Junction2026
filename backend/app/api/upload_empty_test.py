"""A 0-byte upload is rejected before anything is stored or queued (#15)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import documents
from app.config import get_settings
from app.db import get_db
from app.envelope import install_error_handlers


class NoDatabase:
    """Stands in for the session: an empty upload must be rejected before the DB is used."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"database used for an empty upload: {name}")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("VALKEY_URL", "redis://unused")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    def enqueue(document_id: str) -> None:
        raise AssertionError("job enqueued for an empty upload")

    monkeypatch.setattr(documents, "enqueue_ingest", enqueue)
    monkeypatch.setattr(documents, "publish_event", lambda event: None)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(documents.router)
    app.dependency_overrides[get_db] = NoDatabase
    yield TestClient(app, raise_server_exceptions=False)
    get_settings.cache_clear()


def test_empty_file_is_rejected_with_an_envelope_error(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/api/documents", files={"file": ("empty.pdf", b"")})
    assert response.status_code == 400
    assert response.json() == {
        "ok": False,
        "data": None,
        "error": {"code": "empty_file", "message": "The file is empty"},
    }
    assert list(tmp_path.rglob("*")) == []  # no document directory, no 0-byte file
