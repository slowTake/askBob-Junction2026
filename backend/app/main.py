"""FastAPI entrypoint: `uvicorn app.main:app`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ask, documents, events, health, upscale
from app.auth import install_auth
from app.config import get_settings
from app.db import init_db
from app.envelope import install_error_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="bobBuilder", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)
install_auth(app, get_settings().app_password)  # D-048: off when unset
for module in (health, documents, upscale, events, ask):
    app.include_router(module.router)
