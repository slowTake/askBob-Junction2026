"""The password gate in front of /api (D-048)."""

import hashlib
import hmac

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import COOKIE, install_auth, is_open_path, session_token
from app.envelope import install_error_handlers, ok


def make_client(password: str | None) -> TestClient:
    app = FastAPI()
    install_error_handlers(app)
    install_auth(app, password)

    @app.get("/api/documents")
    def documents() -> dict[str, object]:
        return ok([])

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return ok({"postgres": True})

    return TestClient(app)


def test_session_token_is_hmac_sha256_of_a_fixed_label_keyed_by_the_password() -> None:
    # Hand-built reference with the standard library, not by calling the code under test.
    expected = hmac.new(b"pw", b"askbob-session-v1", hashlib.sha256).hexdigest()
    assert session_token("pw") == expected
    assert session_token("pw") != session_token("pw2")  # a new password logs everyone out


def test_open_paths_are_health_login_and_session_only() -> None:
    assert is_open_path("/api/health")
    assert is_open_path("/api/login")
    assert is_open_path("/api/session")
    assert not is_open_path("/api/ask")
    assert not is_open_path("/api/documents")
    assert not is_open_path("/api/healthz")
    assert not is_open_path("/api/login/x")


def test_without_a_password_the_gate_is_off() -> None:
    client = make_client(None)
    assert client.get("/api/documents").status_code == 200
    assert client.get("/api/session").json()["data"] == {"required": False, "authenticated": True}


def test_an_empty_password_setting_also_turns_the_gate_off() -> None:
    assert make_client("").get("/api/documents").status_code == 200


def test_api_needs_the_cookie_but_health_does_not() -> None:
    client = make_client("open sesame")
    response = client.get("/api/documents")
    assert response.status_code == 401
    assert response.json() == {
        "ok": False,
        "data": None,
        "error": {"code": "unauthorized", "message": "Log in first"},
    }
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/session").json()["data"] == {"required": True, "authenticated": False}


def test_wrong_password_is_refused_and_sets_no_cookie() -> None:
    client = make_client("open sesame")
    response = client.post("/api/login", json={"password": "open sesame "})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "wrong_password"
    assert COOKIE not in response.cookies
    assert client.get("/api/documents").status_code == 401


def test_right_password_sets_an_httponly_cookie_that_opens_the_api() -> None:
    client = make_client("open sesame")
    response = client.post("/api/login", json={"password": "open sesame"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "data": {"authenticated": True}, "error": None}
    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert client.get("/api/documents").status_code == 200
    assert client.get("/api/session").json()["data"] == {"required": True, "authenticated": True}


def test_a_forged_cookie_is_refused() -> None:
    client = make_client("open sesame")
    client.cookies.set(COOKIE, session_token("guess"))
    assert client.get("/api/documents").status_code == 401


def test_logout_clears_the_cookie() -> None:
    client = make_client("open sesame")
    client.post("/api/login", json={"password": "open sesame"})
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/documents").status_code == 401


def test_a_malformed_login_body_uses_the_envelope() -> None:
    response = make_client("open sesame").post("/api/login", json={"pw": 1})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_a_non_ascii_cookie_is_refused_not_a_server_error() -> None:
    client = make_client("open sesame")
    response = client.get(
        "/api/documents", headers={"cookie": "bob_session=\xe9".encode("latin-1")}
    )
    assert response.status_code == 401
    session = client.get("/api/session", headers={"cookie": "bob_session=\xe9".encode("latin-1")})
    assert session.status_code == 200
    assert session.json()["data"] == {"required": True, "authenticated": False}


def test_head_and_a_trailing_slash_are_gated_too() -> None:
    client = make_client("open sesame")
    assert client.head("/api/documents").status_code == 401
    assert client.get("/api/documents/").status_code == 401
