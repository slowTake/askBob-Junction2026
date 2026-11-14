from datetime import UTC, datetime, timedelta

from app.domain.recovery import DocumentState, stranded

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
LONG_AGO = NOW - timedelta(minutes=10)


def doc(doc_id: str, status: str, created_at: datetime = LONG_AGO) -> DocumentState:
    return DocumentState(doc_id, status, created_at)


def test_queued_or_processing_documents_without_a_job_are_stranded() -> None:
    docs = [doc("a", "queued"), doc("b", "processing")]
    assert stranded(docs, with_job=set(), now=NOW) == ["a", "b"]


def test_documents_with_a_job_are_left_alone() -> None:
    docs = [doc("a", "queued"), doc("b", "processing")]
    assert stranded(docs, with_job={"a", "b"}, now=NOW) == []


def test_finished_documents_are_never_stranded() -> None:
    docs = [doc("a", "ready"), doc("b", "failed")]
    assert stranded(docs, with_job=set(), now=NOW) == []


def test_a_fresh_upload_gets_time_to_be_enqueued() -> None:
    # The API commits the row first and enqueues right after; 59 s is inside the 60 s grace.
    assert stranded([doc("a", "queued", NOW - timedelta(seconds=59))], set(), NOW) == []
    assert stranded([doc("a", "queued", NOW - timedelta(seconds=60))], set(), NOW) == ["a"]
