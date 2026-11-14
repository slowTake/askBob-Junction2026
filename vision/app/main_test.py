import io
from typing import Any

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app


def _png(mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (40, 30), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _client(analyse: Any) -> TestClient:
    return TestClient(create_app(lambda: analyse))


def test_analyse_returns_the_analysers_result_in_the_envelope() -> None:
    seen: list[tuple[int, ...]] = []

    def fake(rgb: np.ndarray) -> dict[str, Any]:
        seen.append(rgb.shape)
        return {"rooms": [], "walls": [], "objects": [{"class": "Door", "polygon": []}]}

    with _client(fake) as client:
        response = client.post("/analyse", content=_png())
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "data": {"rooms": [], "walls": [], "objects": [{"class": "Door", "polygon": []}]},
        "error": None,
    }
    assert seen == [(30, 40, 3)]  # height, width, RGB


def test_transparent_png_is_flattened_to_rgb() -> None:
    shapes: list[tuple[int, ...]] = []

    def record(rgb: np.ndarray) -> dict[str, Any]:
        shapes.append(rgb.shape)
        return {}

    with _client(record) as client:
        client.post("/analyse", content=_png("RGBA"))
    assert shapes == [(30, 40, 3)]


def test_unreadable_body_is_a_400_in_the_envelope() -> None:
    with _client(lambda rgb: {}) as client:
        response = client.post("/analyse", content=b"not an image")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unreadable_image"


def test_analyser_errors_never_leak() -> None:
    def broken(rgb: np.ndarray) -> dict[str, Any]:
        raise RuntimeError("secret internal detail")

    with _client(broken) as client:
        response = client.post("/analyse", content=_png())
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "analysis_failed"
    assert "secret" not in response.text


def test_health_reports_the_model_loaded() -> None:
    with _client(lambda rgb: {}) as client:
        assert client.get("/health").json()["data"] == {"model_loaded": True}


def test_unknown_route_keeps_the_envelope() -> None:
    with _client(lambda rgb: {}) as client:
        response = client.get("/nope")
    assert response.status_code == 404
    assert response.json()["ok"] is False
