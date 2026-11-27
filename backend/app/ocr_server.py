"""OCR as an HTTP service (#119), for a host with more compute than the worker's.

    POST /ocr?langs=fin+swe+eng&engine=rapid   body: the page image (PNG/JPEG)
    GET  /health

Runs from the backend image: `uvicorn --factory app.ocr_server:serve --port 8002`.
Needs no database or queue. `OCR_DEVICE` (auto, cpu, cuda) puts RapidOCR on the GPU
when the image was built with onnxruntime-gpu; see docs/verda-setup.md.
"""

import logging
import os
import threading
from collections.abc import Callable
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.ocr_wire import words_to_json
from app.domain.tokens import Word
from app.ingest.rooms import Gray

log = logging.getLogger(__name__)
MAX_PIXELS = 60_000_000  # as the vision service: an A0 sheet at 150 dpi is ~35 Mpx
ENGINES = ("rapid", "tesseract")
Reader = Callable[[Gray, str, str], list[Word]]


def ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None}


def fail(code: str, message: str, status: int) -> JSONResponse:
    body = {"ok": False, "data": None, "error": {"code": code, "message": message}}
    return JSONResponse(body, status_code=status)


def decode(body: bytes) -> Gray | None:
    """8-bit grayscale, or None if it isn't a readable image of a sane size."""
    image = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None or image.size == 0 or image.size > MAX_PIXELS:
        return None
    return image


def pick_device(setting: str, providers: list[str]) -> bool:
    """True to run RapidOCR on CUDA. `auto` uses it when onnxruntime offers it."""
    choice = setting.strip().lower() or "auto"
    if choice not in ("auto", "cpu", "cuda"):
        raise ValueError("OCR_DEVICE must be one of auto, cpu, cuda")
    has_cuda = "CUDAExecutionProvider" in providers
    if choice == "cuda" and not has_cuda:
        raise ValueError("OCR_DEVICE=cuda but onnxruntime has no CUDA provider")
    return has_cuda if choice == "auto" else choice == "cuda"


def create_app(read: Reader) -> FastAPI:
    lock = threading.Lock()  # one page at a time: it already uses every core or the GPU
    app = FastAPI(title="askBob OCR")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return ok({"ready": True})

    @app.post("/ocr", response_model=None)
    async def ocr(
        request: Request, langs: str = "fin+swe+eng", engine: str = "rapid"
    ) -> dict[str, Any] | JSONResponse:
        if engine not in ENGINES:
            return fail("bad_request", "engine must be rapid or tesseract", 400)
        gray = decode(await request.body())
        if gray is None:
            return fail("unreadable_image", "Send a PNG or JPEG image", 400)

        def run() -> list[Word]:
            with lock:
                return read(gray, langs, engine)

        try:
            words = await run_in_threadpool(run)
        except Exception:
            log.exception("OCR failed")
            return fail("ocr_failed", "The page could not be read", 500)
        return ok({"words": words_to_json(words)})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return fail("http_error", "Request failed", exc.status_code)

    @app.exception_handler(Exception)
    async def _any(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return fail("internal_error", "Something went wrong", 500)

    return app


def serve() -> FastAPI:
    """`uvicorn --factory app.ocr_server:serve`: the real service."""
    import onnxruntime

    from app.ingest import ocr

    providers = onnxruntime.get_available_providers()
    if "CUDAExecutionProvider" in providers and hasattr(onnxruntime, "preload_dlls"):
        onnxruntime.preload_dlls()  # the GPU build: load the pip CUDA and cuDNN libraries
    cuda = pick_device(os.environ.get("OCR_DEVICE", "auto"), providers)
    ocr.use_cuda(cuda)
    log.warning("OCR runs RapidOCR on %s", "cuda" if cuda else "cpu")
    return create_app(ocr.ocr_words)
