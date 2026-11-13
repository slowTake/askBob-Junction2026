"""The agent refuses to start without Anthropic credentials (#10)."""

from collections.abc import Iterator

import pytest

from app.config import Settings
from app.qa import agent
from app.qa.agent import AgentError, run_agent
from app.qa.service import MESSAGES
from app.qa.tools import ToolContext

SETTINGS = Settings(database_url="postgresql://unused", valkey_url="redis://unused")


@pytest.fixture
def no_credentials(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    agent._client.cache_clear()
    yield
    agent._client.cache_clear()


def _run() -> None:
    ctx = ToolContext(db=None, scope=[])  # type: ignore[arg-type]  # never reached
    next(run_agent("How many bedrooms are there?", [], ctx, SETTINGS))


def test_missing_key_is_reported_as_not_configured(no_credentials: None) -> None:
    with pytest.raises(AgentError) as raised:
        _run()
    assert raised.value.code == "llm_not_configured"
    # The service turns the code into the user-facing message that exists for this case.
    assert MESSAGES["llm_not_configured"] == "The language model is not configured on the server."


def test_empty_key_is_reported_as_not_configured(
    no_credentials: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # docker compose passes ANTHROPIC_API_KEY through even when it is set but empty.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    with pytest.raises(AgentError) as raised:
        _run()
    assert raised.value.code == "llm_not_configured"
