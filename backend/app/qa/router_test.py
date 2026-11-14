"""The router makes one small model call and never raises (#97). Fake clients only."""

import json
from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest

from app.config import Settings
from app.domain.usage import Usage
from app.qa import agent, verda_agent
from app.qa.router import ROUTER_PROMPT, route

INTENT = {"intent": "count", "kind": "door", "quantity": None, "subtype": None,
          "category": None, "name": None, "number": None, "unit": None, "storey": "3. Sal",
          "refers_to_view": False}  # fmt: skip


def _settings(provider: str, router_model: str | None = None) -> Settings:
    return Settings(database_url="postgresql://unused", valkey_url="redis://unused",
                    llm_provider=provider, router_model=router_model)  # type: ignore[arg-type]  # fmt: skip


class FakeVerda:
    def __init__(self, arguments: str | None = json.dumps(INTENT)) -> None:
        self.requests: list[dict[str, Any]] = []
        self.arguments = arguments
        self.error: Exception | None = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        call = SimpleNamespace(function=SimpleNamespace(name="route", arguments=self.arguments))
        message = SimpleNamespace(tool_calls=[call] if self.arguments is not None else None)
        usage = SimpleNamespace(prompt_tokens=700, completion_tokens=80)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


@pytest.fixture
def verda(monkeypatch: pytest.MonkeyPatch) -> FakeVerda:
    client = FakeVerda()
    monkeypatch.setenv("VERDA_API_KEY", "test-key")
    monkeypatch.setattr(verda_agent, "_client", lambda base_url, key: client)
    return client


def test_verda_router_must_call_the_route_tool_and_counts_its_tokens(verda: FakeVerda) -> None:
    usage = Usage()
    assert route("How many doors on '3. Sal'?", _settings("verda"), usage) == INTENT
    request = verda.requests[0]
    assert request["model"] == "kimi-k3-1-pro"  # the agent's model unless ROUTER_MODEL is set
    assert request["tool_choice"] == {"type": "function", "function": {"name": "route"}}
    assert [m["role"] for m in request["messages"]] == ["system", "user"]
    assert request["messages"][0]["content"] == ROUTER_PROMPT
    assert (usage.input_tokens, usage.output_tokens, usage.requests) == (700, 80, 1)


def test_router_model_can_be_set_apart_from_the_agents(verda: FakeVerda) -> None:
    route("How many doors?", _settings("verda", "deepseek-4-1-flash-1017"), Usage())
    assert verda.requests[0]["model"] == "deepseek-4-1-flash-1017"


@pytest.mark.parametrize("arguments", [None, "not json", "[1, 2]"])
def test_unreadable_output_is_none(verda: FakeVerda, arguments: str | None) -> None:
    verda.arguments = arguments
    assert route("How many doors?", _settings("verda"), Usage()) is None


def test_a_failed_call_is_none_not_an_error(verda: FakeVerda) -> None:
    request = httpx2.Request("POST", "https://inference.verda.com/v1/chat/completions")
    verda.error = openai.APIConnectionError(request=request)
    assert route("How many doors?", _settings("verda"), Usage()) is None


def test_no_verda_key_means_no_call(monkeypatch: pytest.MonkeyPatch, verda: FakeVerda) -> None:
    monkeypatch.setenv("VERDA_API_KEY", " ")
    assert route("How many doors?", _settings("verda"), Usage()) is None
    assert verda.requests == []


class FakeClaude:
    api_key = "test-key"
    auth_token = None
    credentials = None

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.stop_reason = "end_turn"
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        usage = SimpleNamespace(input_tokens=50, output_tokens=80, cache_read_input_tokens=650)
        content = [SimpleNamespace(type="thinking"),
                   SimpleNamespace(type="text", text=json.dumps(INTENT))]  # fmt: skip
        return SimpleNamespace(content=content, stop_reason=self.stop_reason, usage=usage)


@pytest.fixture
def claude(monkeypatch: pytest.MonkeyPatch) -> FakeClaude:
    client = FakeClaude()
    monkeypatch.setattr(agent, "_client", lambda: client)
    return client


def test_claude_router_asks_for_the_schema_at_low_effort(claude: FakeClaude) -> None:
    usage = Usage()
    assert route("How many doors on '3. Sal'?", _settings("anthropic"), usage) == INTENT
    request = claude.requests[0]
    assert request["model"] == "claude-opus-5-5"
    assert request["output_config"]["effort"] == "low"
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert "tools" not in request and "tool_choice" not in request
    # 50 uncached + 650 read from the prompt cache.
    assert (usage.input_tokens, usage.cache_read_tokens, usage.output_tokens) == (50, 650, 80)


def test_a_refused_or_cut_off_claude_reply_is_none(claude: FakeClaude) -> None:
    claude.stop_reason = "refusal"
    assert route("How many doors?", _settings("anthropic"), Usage()) is None
