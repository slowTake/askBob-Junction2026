import io
import json
import urllib.error
from typing import Any

import numpy as np
import pytest

from app.config import Settings
from app.domain.tokens import Word
from app.ingest import ocr_client
from app.ingest.ocr_client import page_words

LOCAL = [Word((0, 0, 1, 1), "local", 1.0)]
GRAY = np.full((20, 30), 255, np.uint8)


def _settings(url: str | None) -> Settings:
    return Settings.model_construct(
        ocr_url=url, ocr_timeout_s=7, ocr_langs="fin+eng", ocr_engine="rapid"
    )


class _Response(io.BytesIO):
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


@pytest.fixture
def local(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    def fake(gray: Any, langs: str, engine: str = "rapid") -> list[Word]:
        calls.append((langs, engine))
        return LOCAL

    monkeypatch.setattr(ocr_client, "ocr_words", fake)
    return calls


def _serve(monkeypatch: pytest.MonkeyPatch, answer: Any) -> list[Any]:
    calls: list[Any] = []

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        calls.append((request.full_url, request.get_header("Content-type"), timeout))
        if isinstance(answer, Exception):
            raise answer
        return _Response(answer if isinstance(answer, bytes) else json.dumps(answer).encode())

    monkeypatch.setattr(ocr_client.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_without_a_url_ocr_runs_locally(local: list[Any], monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _serve(monkeypatch, AssertionError("must not call"))
    assert page_words(GRAY, _settings(None)) == LOCAL
    assert local == [("fin+eng", "rapid")]
    assert calls == []


def test_the_services_words_are_used(local: list[Any], monkeypatch: pytest.MonkeyPatch) -> None:
    answer = {
        "ok": True,
        "data": {"words": [{"bbox": [1, 2, 3, 4], "text": "WC", "confidence": 0.9}]},
    }
    calls = _serve(monkeypatch, answer)
    assert page_words(GRAY, _settings("http://gpu:8002/")) == [Word((1, 2, 3, 4), "WC", 0.9)]
    assert local == []
    url, content_type, timeout = calls[0]
    assert url == "http://gpu:8002/ocr?langs=fin%2Beng&engine=rapid"
    assert content_type == "image/png"
    assert timeout == 7


@pytest.mark.parametrize(
    "answer",
    [
        urllib.error.URLError("refused"),
        TimeoutError(),
        b"not json",
        {"ok": False, "data": None, "error": {"code": "x", "message": "y"}},
        {"ok": True, "data": {"words": "garbage"}},
    ],
)
def test_any_failure_falls_back_to_local_ocr(
    answer: Any, local: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _serve(monkeypatch, answer)
    assert page_words(GRAY, _settings("http://gpu:8002")) == LOCAL
    assert local == [("fin+eng", "rapid")]
