"""Runtime settings, read from the process environment only (never from a file in the repo).

With Aiven, run `source scripts/aiven-env.sh` to export DATABASE_URL and VALKEY_URL
for your shell. See docs/aiven-setup.md.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

Effort = Literal["low", "medium", "high", "xhigh", "max"]
Provider = Literal["anthropic", "verda"]
FastPath = Literal["off", "exact", "all"]


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
    # Recognised count and area questions are answered by the server, not the agent loop
    # (D-038). "exact": only from IFC, CAD and PDF-text elements; "all": also from
    # elements the floor-plan model or OCR found; "off": the agent answers everything.
    fast_path: FastPath = "exact"
    router_model: str | None = None  # the model that sorts questions; unset: the agent's model

    # The floor-plan model service (D-022); unset means ingest uses pixel heuristics.
    vision_url: str | None = None
    vision_timeout_s: int = 90  # optional enrichment must not block the ingest queue for minutes

    # Upscale (#82, D-027): one cheap vision call per page, on demand.
    upscale_model: str = "claude-haiku-5-5"  # with LLM_PROVIDER=verda, `verda_model` is used
    upscale_max_side: int = 1568  # longest side of the image sent, in pixels
    upscale_timeout_s: float = 90.0
    # Sketch redraw (#82): on raster image pages a stronger model authors the whole plan,
    # then checks a render of its draft against the photo and corrects it.
    sketch_model: str = "claude-opus-5-5"
    sketch_effort: Effort = "high"  # technical drawings read better from high up
    sketch_max_rounds: int = Field(default=3, ge=1, le=6)  # the first draft plus checks
    sketch_max_side: int = 2576  # Opus 5.5 reads images up to 2576 px on the long edge
    sketch_timeout_s: float = 300.0  # one model call
    sketch_deadline_s: float = 600.0  # no new check round starts after this

    # OCR service on a bigger host (#119); unset means the worker reads pages itself.
    ocr_url: str | None = None
    ocr_timeout_s: int = 120  # then the page is read locally after all

    render_dpi: int = 150
    ocr_langs: str = "fin+swe+eng"  # Tesseract only
    ocr_engine: Literal["rapid", "tesseract"] = "rapid"  # D-024; Tesseract is also the fallback
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
