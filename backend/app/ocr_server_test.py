from typing import Any

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.domain.tokens import Word
from app.ocr_server import create_app, pick_device


def _png(height: int = 30, width: int = 40, channels: int = 3) -> bytes:
    ok, buf = cv2.imencode(".png", np.full((height, width, channels), 255, np.uint8))
    assert ok
    return buf.tobytes()


def _client(read: Any) -> TestClient:
    return TestClient(create_app(read))


def test_ocr_returns_the_words_in_the_envelope() -> None:
    seen: list[Any] = []

    def read(gray: Any, langs: str, engine: str) -> list[Word]:
        seen.append((gray.shape, gray.dtype, langs, engine))
        return [Word((1, 2, 3, 4), "WC", 0.9)]

    with _client(read) as client:
        response = client.post("/ocr?langs=fin%2Beng&engine=tesseract", content=_png())
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "data": {"words": [{"bbox": [1.0, 2.0, 3.0, 4.0], "text": "WC", "confidence": 0.9}]},
        "error": None,
    }
    assert seen == [((30, 40), np.dtype("uint8"), "fin+eng", "tesseract")]  # grayscale


def test_defaults_match_the_workers_defaults() -> None:
    seen: list[Any] = []

    def read(gray: Any, langs: str, engine: str) -> list[Word]:
        seen.append((langs, engine))
        return []

    with _client(read) as client:
        client.post("/ocr", content=_png())
    assert seen == [("fin+swe+eng", "rapid")]


def test_an_unknown_engine_is_a_400() -> None:
    with _client(lambda *a: []) as client:
        response = client.post("/ocr?engine=magic", content=_png())
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_not_an_image_is_a_400() -> None:
    with _client(lambda *a: []) as client:
        response = client.post("/ocr", content=b"hello")
    assert response.status_code == 400
    assert response.json() == {
        "ok": False,
        "data": None,
        "error": {"code": "unreadable_image", "message": "Send a PNG or JPEG image"},
    }


def test_a_failure_never_leaks_its_message() -> None:
    def boom(*a: Any) -> list[Word]:
        raise RuntimeError("secret stack detail")

    with _client(boom) as client:
        response = client.post("/ocr", content=_png())
    assert response.status_code == 500
    assert "secret" not in response.text
    assert response.json()["error"]["code"] == "ocr_failed"


def test_health_and_unknown_routes_use_the_envelope() -> None:
    with _client(lambda *a: []) as client:
        assert client.get("/health").json() == {"ok": True, "data": {"ready": True}, "error": None}
        missing = client.get("/nope")
    assert missing.status_code == 404
    assert missing.json()["ok"] is False


@pytest.mark.parametrize(
    ("setting", "providers", "expected"),
    [
        ("auto", ["CUDAExecutionProvider", "CPUExecutionProvider"], True),
        ("auto", ["CPUExecutionProvider"], False),
        ("", ["CUDAExecutionProvider"], True),
        ("cpu", ["CUDAExecutionProvider"], False),
        (" CUDA ", ["CUDAExecutionProvider"], True),
    ],
)
def test_pick_device(setting: str, providers: list[str], expected: bool) -> None:
    assert pick_device(setting, providers) is expected


@pytest.mark.parametrize("setting", ["cuda", "tpu"])
def test_pick_device_refuses_what_it_cannot_do(setting: str) -> None:
    # Forcing CUDA where onnxruntime has none must stop startup, not run slowly on the CPU.
    with pytest.raises(ValueError):
        pick_device(setting, ["CPUExecutionProvider"])
