"""One response shape for every endpoint (RULES.md §4).

    {"ok": true,  "data": ..., "error": null}
    {"ok": false, "data": null, "error": {"code": "not_found", "message": "Document not found"}}

Raw exception text never reaches the client: unexpected errors are logged here and
answered with a generic message.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class AppError(Exception):
    """An error whose message is safe to show to users. Write the message yourself."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None}


def fail(code: str, message: str, status: int) -> JSONResponse:
    body = {"ok": False, "data": None, "error": {"code": code, "message": message}}
    return JSONResponse(body, status_code=status)


_HTTP_CODES = {404: "not_found", 405: "method_not_allowed", 413: "too_large"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return fail(exc.code, exc.message, exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return fail(code, "Request failed", exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        log.info("validation error: %s", exc.errors())
        return fail("validation_error", "The request is not valid", 422)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return fail("internal_error", "Something went wrong", 500)
