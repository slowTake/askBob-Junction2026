"""Which documents wait for an ingest job that no longer exists.

A document is `queued` or `processing` while a job works on it. If Valkey lost the job
(a restart without persistence, a crash between the database commit and the enqueue),
nothing would ever pick the document up again, and the UI would show "Queued" forever.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

IN_FLIGHT = ("queued", "processing")
GRACE = timedelta(seconds=60)  # uploads commit first and enqueue right after


@dataclass(frozen=True)
class DocumentState:
    id: str
    status: str
    created_at: datetime


def stranded(docs: list[DocumentState], with_job: set[str], now: datetime) -> list[str]:
    """Ids of in-flight documents that no queued or running job refers to."""
    return [
        d.id
        for d in docs
        if d.status in IN_FLIGHT and d.id not in with_job and now - d.created_at >= GRACE
    ]
