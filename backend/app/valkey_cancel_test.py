"""Deleting a document cancels its ingest job (#120), so the one worker is free at once."""

from types import SimpleNamespace
from typing import Any

import pytest
import redis
from rq.exceptions import InvalidJobOperation

from app import valkey


class _Job:
    def __init__(self, job_id: str, doc: str) -> None:
        self.id, self.args, self.cancelled = job_id, (doc,), False

    def cancel(self) -> None:
        self.cancelled = True


@pytest.fixture
def queue(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state = SimpleNamespace(
        queued={"j1": _Job("j1", "doc-a"), "j2": _Job("j2", "doc-b")},
        started={"j3": _Job("j3", "doc-a")},
        stopped=[],
        stop_error=None,
    )
    fake_queue = SimpleNamespace(connection="conn", get_job_ids=lambda: list(state.queued))
    monkeypatch.setattr(valkey, "ingest_queue", lambda: fake_queue)
    monkeypatch.setattr(
        valkey,
        "StartedJobRegistry",
        lambda queue: SimpleNamespace(get_job_ids=lambda: list(state.started)),
    )
    jobs = {**state.queued, **state.started}
    monkeypatch.setattr(
        valkey.Job, "fetch_many", lambda ids, connection: [jobs.get(i) for i in ids]
    )

    def stop(connection: Any, job_id: str) -> None:
        if state.stop_error:
            raise state.stop_error
        state.stopped.append(job_id)

    monkeypatch.setattr(valkey, "send_stop_job_command", stop)
    return state


def test_a_waiting_job_is_cancelled_and_a_running_one_stopped(queue: SimpleNamespace) -> None:
    valkey.cancel_ingest("doc-a")
    assert queue.queued["j1"].cancelled is True
    assert queue.stopped == ["j3"]


def test_other_documents_jobs_are_left_alone(queue: SimpleNamespace) -> None:
    valkey.cancel_ingest("doc-a")
    assert queue.queued["j2"].cancelled is False


def test_a_job_that_just_finished_is_not_an_error(queue: SimpleNamespace) -> None:
    queue.stop_error = InvalidJobOperation("Job is not currently executing")
    valkey.cancel_ingest("doc-a")  # no raise
    assert queue.queued["j1"].cancelled is True


def test_valkey_down_never_fails_the_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    def down() -> Any:
        raise redis.ConnectionError("down")

    monkeypatch.setattr(valkey, "ingest_queue", down)
    valkey.cancel_ingest("doc-a")  # no raise
