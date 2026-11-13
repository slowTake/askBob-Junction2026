"""Live ingest progress: Valkey pub/sub -> server-sent events for the browser."""

import asyncio
import logging
from collections.abc import AsyncIterator

import redis.asyncio as aioredis
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.domain.streams import sse
from app.valkey import EVENTS_CHANNEL

router = APIRouter(prefix="/api", tags=["events"])
log = logging.getLogger(__name__)
KEEPALIVE_S = 15.0
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    return StreamingResponse(_stream(request), media_type="text/event-stream", headers=SSE_HEADERS)


async def _stream(request: Request) -> AsyncIterator[str]:
    client = aioredis.Redis.from_url(get_settings().valkey_url)
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(EVENTS_CHANNEL)
        yield ": connected\n\n"
        idle = 0.0
        while not await request.is_disconnected():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                idle += 1.0
                if idle >= KEEPALIVE_S:
                    idle = 0.0
                    yield ": keepalive\n\n"
                continue
            idle = 0.0
            data = message["data"]
            text = data.decode() if isinstance(data, bytes) else str(data)
            yield f"event: document\ndata: {text}\n\n"
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("event stream failed")
        yield sse("error", {"code": "events_unavailable", "message": "Live updates paused"})
    finally:
        await pubsub.aclose()
        await client.aclose()
