"""Aiven for Valkey: ingest job queue (RQ), live progress events (pub/sub), answer cache.

Valkey speaks the Redis protocol, so the standard `redis` and `rq` clients work.
Aiven URIs use `rediss://` (TLS), which redis-py handles from the URL.
"""

import json
import logging
from functools import lru_cache
from typing import Any

import redis
from rq import Callback, Queue, Worker
from rq.job import Job
from rq.registry import StartedJobRegistry

from app.config import get_settings

log = logging.getLogger(__name__)

EVENTS_CHANNEL = "bob:events"
INGEST_QUEUE = "ingest"
INGEST_JOB = "app.ingest.jobs.ingest_document"
# By name, like the job itself: importing app.ingest.jobs here would be circular.
INGEST_FAILED = "app.ingest.jobs.on_ingest_failure"


class QueueError(Exception):
    """The ingest job could not be enqueued (Valkey unreachable)."""


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().valkey_url, health_check_interval=30)


def ingest_queue() -> Queue:
    return Queue(INGEST_QUEUE, connection=get_redis())


def enqueue_ingest(document_id: str) -> None:
    """Raises QueueError when Valkey cannot take the job."""
    try:
        ingest_queue().enqueue_call(
            INGEST_JOB,
            args=(document_id,),
            timeout=1800,
            result_ttl=3600,
            failure_ttl=86_400,
            on_failure=Callback(INGEST_FAILED),
        )
    except redis.RedisError as exc:
        raise QueueError("could not enqueue the ingest job") from exc


def in_flight_document_ids() -> set[str]:
    """Documents that a queued or running ingest job refers to.

    Listing the started jobs also cleans up the ones a dead worker abandoned: RQ moves
    them to the failed registry and runs their failure callback first.
    """
    queue = ingest_queue()
    job_ids = [*queue.get_job_ids(), *StartedJobRegistry(queue=queue).get_job_ids()]
    jobs = Job.fetch_many(job_ids, connection=queue.connection)
    return {str(job.args[0]) for job in jobs if job is not None and job.args}


def ingest_worker_count() -> int:
    """Workers listening on the ingest queue. Zero means uploads wait until one starts."""
    return Worker.count(queue=ingest_queue())


def publish_event(event: dict[str, Any]) -> None:
    """Fire-and-forget: progress events are a UX nicety, never a reason to fail a job."""
    try:
        get_redis().publish(EVENTS_CHANNEL, json.dumps(event))
    except redis.RedisError:
        log.warning("could not publish event %s", event.get("type"), exc_info=True)


def cache_get(key: str) -> dict[str, Any] | None:
    try:
        raw = get_redis().get(key)
    except redis.RedisError:
        log.warning("answer cache read failed", exc_info=True)
        return None
    return json.loads(raw) if isinstance(raw, bytes | str) else None


def cache_set(key: str, value: dict[str, Any], ttl_s: int) -> None:
    try:
        get_redis().set(key, json.dumps(value), ex=ttl_s)
    except redis.RedisError:
        log.warning("answer cache write failed", exc_info=True)
