import logging
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.db import get_engine
from app.valkey import get_redis, ingest_worker_count

router = APIRouter(prefix="/api", tags=["health"])
log = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict[str, Any]:
    """Report whether Postgres and Valkey answer, and how many ingest workers listen.

    Always 200. `ok` covers the API's own services only: without a worker, uploads wait
    in the queue (`ingest_workers` is 0) but everything else works.
    """
    status = {"postgres": False, "valkey": False}
    workers: int | None = None
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        status["postgres"] = True
    except Exception:
        log.warning("health: postgres unreachable", exc_info=True)
    try:
        status["valkey"] = bool(get_redis().ping())
        workers = ingest_worker_count()
    except Exception:
        log.warning("health: valkey unreachable", exc_info=True)
    return {
        "ok": all(status.values()),
        "data": {**status, "ingest_workers": workers},
        "error": None,
    }
