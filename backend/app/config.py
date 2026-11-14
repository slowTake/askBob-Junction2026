"""Runtime settings, read from the process environment only (never from a file in the repo).

With Aiven, run `source scripts/aiven-env.sh` to export DATABASE_URL and VALKEY_URL
for your shell. See docs/aiven-setup.md.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings

Effort = Literal["low", "medium", "high", "xhigh", "max"]
Provider = Literal["anthropic", "verda"]


class Settings(BaseSettings):
    database_url: str
    valkey_url: str
    data_dir: Path = Path("/data")

    llm_provider: Provider = "anthropic"
    claude_model: str = "claude-opus-5-5"
    claude_effort: Effort = "high"
    verda_model: str = "kimi-k3-1-pro"
    verda_base_url: str = "https://inference.verda.com/v1"
    max_agent_turns: int = 12

    # The floor-plan model service (D-022); unset means ingest uses pixel heuristics.
    vision_url: str | None = None
    vision_timeout_s: int = 90  # optional enrichment must not block the ingest queue for minutes

    render_dpi: int = 150
    ocr_langs: str = "fin+swe+eng"
    max_upload_mb: int = 200
    answer_cache_ttl_s: int = 86_400
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    @field_validator("database_url", "valkey_url")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("is empty: run `source scripts/aiven-env.sh` or `make up-local`")
        return value

    @property
    def llm_model(self) -> str:
        """The model answering questions, for the answer-cache key and `qa_log`."""
        return self.verda_model if self.llm_provider == "verda" else self.claude_model

    @property
    def sqlalchemy_url(self) -> str:
        return normalize_database_url(self.database_url)


def normalize_database_url(url: str) -> str:
    """Aiven hands out `postgres://...?sslmode=require`; SQLAlchemy needs the driver name."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
