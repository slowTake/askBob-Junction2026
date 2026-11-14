from app.domain.ingest_errors import MESSAGES, error_message


def test_known_and_unknown_codes() -> None:
    assert error_message("encrypted_pdf") == MESSAGES["encrypted_pdf"]
    assert error_message("something_new") == MESSAGES["ingest_failed"]
    assert error_message(None) is None


def test_interrupted_and_killed_jobs_get_their_own_message() -> None:
    # A restart and an out-of-memory kill are not the file's fault: say so, not "try again".
    assert "interrupted" in (error_message("ingest_interrupted") or "")
    assert "memory" in (error_message("ingest_killed") or "")
