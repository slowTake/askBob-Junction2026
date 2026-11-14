from app.config import Settings, normalize_database_url


def test_aiven_uri_gets_psycopg_driver_and_keeps_sslmode() -> None:
    url = "postgres://avnadmin:pw@pg-x.aivencloud.com:12345/defaultdb?sslmode=require"
    assert normalize_database_url(url) == (
        "postgresql+psycopg://avnadmin:pw@pg-x.aivencloud.com:12345/defaultdb?sslmode=require"
    )


def test_postgresql_scheme_is_normalized_too() -> None:
    assert normalize_database_url("postgresql://u@h/db") == "postgresql+psycopg://u@h/db"


def test_explicit_driver_is_left_alone() -> None:
    assert normalize_database_url("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"


def test_llm_model_follows_the_provider() -> None:
    default = Settings(database_url="postgresql://u@h/db", valkey_url="redis://h")
    verda = Settings(
        database_url="postgresql://u@h/db", valkey_url="redis://h", llm_provider="verda"
    )
    assert default.llm_model == "claude-opus-5-5"  # default provider is anthropic
    assert verda.llm_model == "kimi-k3-1-pro"


def test_vision_wait_is_bounded_and_can_be_overridden() -> None:
    settings = Settings(database_url="postgresql://u@h/db", valkey_url="redis://h")
    assert settings.vision_timeout_s == 90
    configured = Settings(
        database_url="postgresql://u@h/db", valkey_url="redis://h", vision_timeout_s=20
    )
    assert configured.vision_timeout_s == 20
