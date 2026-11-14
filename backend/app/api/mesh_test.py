"""Documents ingested before meshes were gzipped keep their 3D model (PR #65 review)."""

import gzip
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import documents
from app.config import get_settings
from app.envelope import install_error_handlers
from app.storage import document_dir


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("VALKEY_URL", "redis://unused")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(documents.router)
    yield TestClient(app, raise_server_exceptions=False)
    get_settings.cache_clear()


def test_a_mesh_stored_before_gzip_is_still_served(client: TestClient) -> None:
    doc_id = uuid.uuid4()
    folder = document_dir(doc_id)
    folder.mkdir(parents=True)
    (folder / "mesh.json").write_text('{"meshes": []}')
    response = client.get(f"/api/documents/{doc_id}/mesh")
    assert response.status_code == 200
    assert response.json() == {"meshes": []}


def test_a_gzipped_mesh_is_served_compressed(client: TestClient) -> None:
    doc_id = uuid.uuid4()
    folder = document_dir(doc_id)
    folder.mkdir(parents=True)
    (folder / "mesh.json.gz").write_bytes(gzip.compress(b'{"meshes": [1]}'))
    response = client.get(f"/api/documents/{doc_id}/mesh")
    assert response.status_code == 200
    assert response.json() == {"meshes": [1]}  # the client decompresses via Content-Encoding
