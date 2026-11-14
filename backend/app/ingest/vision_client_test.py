import io
import json
import urllib.error
from typing import Any

import pytest

from app.config import Settings
from app.ingest import vision_client
from app.ingest.vision_client import analyse_page


def _settings(url: str | None = "http://vision:8001") -> Settings:
    return Settings.model_construct(vision_url=url, vision_timeout_s=5)


class _Response(io.BytesIO):
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def _serve(monkeypatch: pytest.MonkeyPatch, answer: Any) -> list[Any]:
    calls: list[Any] = []

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        calls.append((request.full_url, request.get_header("Content-type"), timeout))
        if isinstance(answer, Exception):
            raise answer
        return _Response(answer if isinstance(answer, bytes) else json.dumps(answer).encode())

    monkeypatch.setattr(vision_client.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_returns_the_parsed_result_when_the_service_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    door = {"class": "Door", "polygon": [[0, 0], [10, 0], [10, 2], [0, 2]]}
    calls = _serve(monkeypatch, {"ok": True, "data": {"objects": [door]}, "error": None})
    parsed, status = analyse_page(b"png", _settings())
    assert status == "used"
    assert parsed is not None and [o.cls for o in parsed.objects] == ["Door"]
    assert calls == [("http://vision:8001/analyse", "image/png", 5)]


def test_not_configured_means_unavailable_without_a_call(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _serve(monkeypatch, {"ok": True, "data": {}})
    assert analyse_page(b"png", _settings(url=None)) == (None, "unavailable")
    assert calls == []


def test_unreachable_service_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, urllib.error.URLError(ConnectionRefusedError()))
    assert analyse_page(b"png", _settings()) == (None, "unavailable")


def test_timeout_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, TimeoutError())
    assert analyse_page(b"png", _settings()) == (None, "failed")
    _serve(monkeypatch, urllib.error.URLError(TimeoutError()))
    assert analyse_page(b"png", _settings()) == (None, "failed")


def test_error_envelope_or_garbage_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, {"ok": False, "data": None, "error": {"code": "analysis_failed"}})
    assert analyse_page(b"png", _settings()) == (None, "failed")
    _serve(monkeypatch, b"<html>bad gateway</html>")
    assert analyse_page(b"png", _settings()) == (None, "failed")


def test_http_error_status_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    error = urllib.error.HTTPError("http://vision:8001/analyse", 500, "boom", {}, None)  # type: ignore[arg-type]
    _serve(monkeypatch, error)
    assert analyse_page(b"png", _settings()) == (None, "failed")
