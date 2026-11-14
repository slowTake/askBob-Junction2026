"""Internal HTTP service: POST a page image, get the plan's polygons back.

    POST /analyse   body: the image bytes (PNG/JPEG/...)
    GET  /health

Every response uses the app's envelope (RULES.md §4):
    {"ok": true, "data": ..., "error": null}
    {"ok": false, "data": null, "error": {"code": "...", "message": "..."}}
"""

import io
import logging
import os
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)
MAX_PIXELS = 60_000_000  # an A0 sheet at 150 dpi is ~35 Mpx
Analyser = Callable[[np.ndarray], dict[str, Any]]


def ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None}


def fail(code: str, message: str, status: int) -> JSONResponse:
    body = {"ok": False, "data": None, "error": {"code": code, "message": message}}
    return JSONResponse(body, status_code=status)


def decode(body: bytes) -> np.ndarray | None:
    """RGB array, transparent areas on white; None if it isn't a readable image."""
    try:
        img: Image.Image = Image.open(io.BytesIO(body))
        if img.width * img.height > MAX_PIXELS:
            return None
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            white = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(white, img)
        return np.asarray(img.convert("RGB")).copy()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None


def create_app(load: Callable[[], Analyser]) -> FastAPI:
    """`load` builds the analyser once, at startup (the model takes a few seconds)."""
    lock = threading.Lock()  # one page at a time: the model uses all CPU cores or the GPU
    state: dict[str, Analyser] = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        state["analyse"] = await run_in_threadpool(load)
        yield

    app = FastAPI(title="bobBuilder vision", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return ok({"model_loaded": "analyse" in state})

    @app.post("/analyse", response_model=None)
    async def analyse(request: Request) -> dict[str, Any] | JSONResponse:
        rgb = decode(await request.body())
        if rgb is None:
            return fail("unreadable_image", "Send a PNG or JPEG image under 60 megapixels", 400)
        if "analyse" not in state:
            return fail("not_ready", "The model is still loading", 503)

        def run() -> dict[str, Any]:
            with lock:
                return state["analyse"](rgb)

        try:
            return ok(await run_in_threadpool(run))
        except Exception:
            log.exception("analysis failed")
            return fail("analysis_failed", "The plan could not be analysed", 500)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return fail("http_error", "Request failed", exc.status_code)

    @app.exception_handler(Exception)
    async def _any(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return fail("internal_error", "Something went wrong", 500)

    return app


def _load_model() -> Analyser:
    import torch

    from app.analyse import analyse
    from app.device import pick_device
    from app.model import FloorplanModel

    weights = Path(os.environ.get("VISION_WEIGHTS", "/opt/weights/cubicasa.pt"))
    device = pick_device(os.environ.get("VISION_DEVICE", "auto"), torch.cuda.is_available())
    log.warning("vision model runs on %s", device)
    rotations = int(os.environ.get("VISION_ROTATIONS", "1"))
    model = FloorplanModel(weights, rotations=rotations, device=device)
    return lambda rgb: analyse(model, rgb)


def serve() -> FastAPI:
    """`uvicorn --factory app.main:serve`: the real service, with the model."""
    return create_app(_load_model)
