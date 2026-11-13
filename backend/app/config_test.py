from app.config import normalize_database_url


def test_aiven_uri_gets_psycopg_driver_and_keeps_sslmode() -> None:
    url = "postgres://avnadmin:pw@pg-x.aivencloud.com:12345/defaultdb?sslmode=require"
    assert normalize_database_url(url) == (
        "postgresql+psycopg://avnadmin:pw@pg-x.aivencloud.com:12345/defaultdb?sslmode=require"
    )


def test_postgresql_scheme_is_normalized_too() -> None:
    assert normalize_database_url("postgresql://u@h/db") == "postgresql+psycopg://u@h/db"


def test_explicit_driver_is_left_alone() -> None:
    assert normalize_database_url("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"
