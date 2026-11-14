from app.domain.ingest_errors import MESSAGES, error_message


def test_known_and_unknown_codes() -> None:
    assert error_message("encrypted_pdf") == MESSAGES["encrypted_pdf"]
    assert error_message("something_new") == MESSAGES["ingest_failed"]
    assert error_message(None) is None
