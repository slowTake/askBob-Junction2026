"""An ingest job never leaves its document waiting: any failure ends as `failed`."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, cast

import pytest
from rq.exceptions import AbandonedJobError
from rq.job import Job

from app.ingest import jobs

DOC_ID = "5bb56215-0000-4000-8000-000000000001"


class FakeDoc:
    def __init__(self, status: str) -> None:
        self.status = status
        self.error_code: str | None = None
        self.kind = "pdf"
        self.meta: dict[str, Any] = {}


class FakeSession:
    def __init__(self, doc: FakeDoc | None) -> None:
        self.doc = doc

    def get(self, model: object, key: object) -> FakeDoc | None:
        return self.doc


class FakeJob:
    args = (DOC_ID,)


JOB = cast(Job, FakeJob())  # the callbacks only read `args`


def scopes(*steps: FakeSession | Exception) -> Callable[[], Any]:
    """A session_scope stand-in: each use takes the next session, or raises the next error."""
    remaining = iter(steps)

    @contextmanager
    def session_scope() -> Iterator[FakeSession]:
        step = next(remaining)
        if isinstance(step, Exception):
            raise step
        yield step

    return session_scope


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(jobs, "publish_event", sent.append)
    return sent


def test_a_failing_first_database_write_still_marks_the_document_failed(
    monkeypatch: pytest.MonkeyPatch, events: list[dict[str, Any]]
) -> None:
    # #56: the write that sets `processing` raised, and the document stayed `queued` forever.
    doc = FakeDoc("queued")
    broken = RuntimeError('prepared statement "_pg3_0" already exists')
    monkeypatch.setattr(jobs, "session_scope", scopes(broken, FakeSession(doc)))
    jobs.ingest_document(DOC_ID)
    assert (doc.status, doc.error_code) == ("failed", "ingest_failed")
    assert [e["status"] for e in events] == ["failed"]


def test_a_finished_document_is_never_marked_failed(
    monkeypatch: pytest.MonkeyPatch, events: list[dict[str, Any]]
) -> None:
    doc = FakeDoc("ready")  # e.g. a late callback for a job that had already succeeded
    monkeypatch.setattr(jobs, "session_scope", scopes(FakeSession(doc)))
    jobs.mark_failed(DOC_ID, "ingest_failed")
    assert doc.status == "ready"
    assert events == []


def test_marking_a_failure_never_raises_when_the_database_is_down(
    monkeypatch: pytest.MonkeyPatch, events: list[dict[str, Any]]
) -> None:
    monkeypatch.setattr(jobs, "session_scope", scopes(ConnectionError("database down")))
    jobs.mark_failed(DOC_ID, "ingest_failed")  # must not raise: it runs inside error handling
    assert events == []


def test_a_job_abandoned_by_a_dead_worker_is_reported_as_interrupted(
    monkeypatch: pytest.MonkeyPatch, events: list[dict[str, Any]]
) -> None:
    doc = FakeDoc("processing")
    monkeypatch.setattr(jobs, "session_scope", scopes(FakeSession(doc)))
    # RQ's registry cleanup calls the failure callback with (type, value, traceback).
    jobs.on_ingest_failure(JOB, None, AbandonedJobError, AbandonedJobError(), None)
    assert (doc.status, doc.error_code) == ("failed", "ingest_interrupted")


def test_a_killed_job_process_is_reported_as_killed(
    monkeypatch: pytest.MonkeyPatch, events: list[dict[str, Any]]
) -> None:
    doc = FakeDoc("processing")
    monkeypatch.setattr(jobs, "session_scope", scopes(FakeSession(doc)))
    jobs.on_work_horse_killed(JOB, 123, 9, None)  # e.g. the kernel's OOM killer (signal 9)
    assert (doc.status, doc.error_code) == ("failed", "ingest_killed")
