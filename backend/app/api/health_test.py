"""Health reports the ingest workers, so the UI can explain a document that waits."""

from typing import Any

import pytest
import redis
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import health


class FakeConnection:
    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, statement: object) -> None:
        return None


class FakeEngine:
    def connect(self) -> FakeConnection:
        return FakeConnection()


class FakeRedis:
    def __init__(self, up: bool) -> None:
        self.up = up

    def ping(self) -> bool:
        if not self.up:
            raise redis.ConnectionError("down")
        return True


def get_health(monkeypatch: pytest.MonkeyPatch, workers: int, valkey_up: bool = True) -> Any:
    monkeypatch.setattr(health, "get_engine", FakeEngine)
    monkeypatch.setattr(health, "get_redis", lambda: FakeRedis(valkey_up))
    monkeypatch.setattr(health, "ingest_worker_count", lambda: workers)
    app = FastAPI()
    app.include_router(health.router)
    return TestClient(app).get("/api/health").json()


def test_health_counts_the_ingest_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    assert get_health(monkeypatch, workers=2) == {
        "ok": True,
        "data": {"postgres": True, "valkey": True, "ingest_workers": 2},
        "error": None,
    }


def test_no_worker_is_reported_but_the_api_stays_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    body = get_health(monkeypatch, workers=0)
    assert body["ok"] is True  # the API answers; only ingest waits
    assert body["data"]["ingest_workers"] == 0


def test_unknown_worker_count_when_valkey_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    body = get_health(monkeypatch, workers=1, valkey_up=False)
    assert body["ok"] is False
    assert body["data"] == {"postgres": True, "valkey": False, "ingest_workers": None}
