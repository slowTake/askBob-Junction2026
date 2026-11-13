"""RULES.md §4: one response shape, and raw errors never reach the client."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.envelope import AppError, install_error_handlers, ok

app = FastAPI()
install_error_handlers(app)


class Body(BaseModel):
    question: str


@app.get("/fine")
def fine() -> dict[str, object]:
    return ok({"value": 1})


@app.get("/known")
def known() -> None:
    raise AppError("not_found", "Document not found", 404)


@app.get("/boom")
def boom() -> None:
    raise RuntimeError("password=hunter2 at db.internal:5432")


@app.post("/validate")
def validate(body: Body) -> dict[str, object]:
    return ok(body.question)


client = TestClient(app, raise_server_exceptions=False)


def test_success_shape() -> None:
    assert client.get("/fine").json() == {"ok": True, "data": {"value": 1}, "error": None}


def test_app_error_shape() -> None:
    response = client.get("/known")
    assert response.status_code == 404
    assert response.json() == {
        "ok": False,
        "data": None,
        "error": {"code": "not_found", "message": "Document not found"},
    }


def test_unexpected_error_is_generic() -> None:
    response = client.get("/boom")
    assert response.status_code == 500
    assert response.json()["error"] == {"code": "internal_error", "message": "Something went wrong"}
    assert "hunter2" not in response.text


def test_validation_error_hides_details() -> None:
    response = client.post("/validate", json={"nope": 1})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "nope" not in response.text


def test_unknown_route_uses_envelope() -> None:
    response = client.get("/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
