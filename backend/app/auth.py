"""A shared-password gate in front of /api (D-048).

It is there so strangers can't spend our model credits: with APP_PASSWORD set, every
/api route except health, login and session answers 401 until the browser has logged in.
Without APP_PASSWORD (local dev, CI) the gate is off.

The session cookie is HMAC-SHA256(password, a fixed label): stateless, the same in every
process, and changing APP_PASSWORD logs everyone out.
"""

import asyncio
import hashlib
import hmac
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, FastAPI, Request, Response
from pydantic import BaseModel

from app.envelope import AppError, fail, ok

COOKIE = "bob_session"
COOKIE_MAX_AGE_S = 12 * 3600  # a demo day
WRONG_PASSWORD_DELAY_S = 0.5  # slows guessing without bothering a person
_LABEL = b"askbob-session-v1"
_OPEN_PATHS = frozenset({"/api/health", "/api/login", "/api/session"})


def session_token(password: str) -> str:
    """The cookie value for a password."""
    return hmac.new(password.encode(), _LABEL, hashlib.sha256).hexdigest()


def is_open_path(path: str) -> bool:
    """Paths that answer without logging in."""
    return path in _OPEN_PATHS


def _valid(cookie: str | None, password: str) -> bool:
    # Compare bytes: compare_digest raises on a str with non-ASCII characters.
    if cookie is None:
        return False
    given = cookie.encode("utf-8", "surrogateescape")
    return hmac.compare_digest(given, session_token(password).encode())


class LoginBody(BaseModel):
    password: str


def install_auth(app: FastAPI, password: str | None) -> None:
    """Add the gate middleware and the login, logout and session routes."""
    gate = password or None  # an empty setting means no gate
    router = APIRouter(prefix="/api", tags=["auth"])

    @router.get("/session")
    def session(request: Request) -> dict[str, Any]:
        authenticated = gate is None or _valid(request.cookies.get(COOKIE), gate)
        return ok({"required": gate is not None, "authenticated": authenticated})

    @router.post("/login")
    async def login(body: LoginBody, response: Response) -> dict[str, Any]:
        if gate is None:
            return ok({"authenticated": True})
        if not hmac.compare_digest(body.password.encode(), gate.encode()):
            await asyncio.sleep(WRONG_PASSWORD_DELAY_S)
            raise AppError("wrong_password", "That password is not right", 401)
        response.set_cookie(
            COOKIE,
            session_token(gate),
            max_age=COOKIE_MAX_AGE_S,
            httponly=True,
            samesite="lax",
            path="/",
        )
        return ok({"authenticated": True})

    @router.post("/logout")
    def logout(response: Response) -> dict[str, Any]:
        response.delete_cookie(COOKIE, path="/")
        return ok({"authenticated": False})

    app.include_router(router)

    if gate is None:
        return

    @app.middleware("http")
    async def _require_login(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if (
            path.startswith("/api/")
            and request.method != "OPTIONS"
            and not is_open_path(path)
            and not _valid(request.cookies.get(COOKIE), gate)
        ):
            return fail("unauthorized", "Log in first", 401)
        return await call_next(request)
