import logging
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.db import get_engine
from app.valkey import get_redis

router = APIRouter(prefix="/api", tags=["health"])
log = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict[str, Any]:
    """Report whether Postgres and Valkey answer. Always 200, with per-service status."""
    status = {"postgres": False, "valkey": False}
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        status["postgres"] = True
    except Exception:
        log.warning("health: postgres unreachable", exc_info=True)
    try:
        status["valkey"] = bool(get_redis().ping())
    except Exception:
        log.warning("health: valkey unreachable", exc_info=True)
    return {"ok": all(status.values()), "data": status, "error": None}
