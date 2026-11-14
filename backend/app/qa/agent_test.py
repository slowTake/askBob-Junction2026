"""The agent refuses to start without Anthropic credentials (#10), and its last turn
is the answer (#95)."""

import copy
import json
import os
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import Settings
from app.qa import agent
from app.qa.agent import AgentError, run_agent
from app.qa.prompts import LAST_STEP_NOTE
from app.qa.service import MESSAGES
from app.qa.tools import ToolContext

SETTINGS = Settings(database_url="postgresql://unused", valkey_url="redis://unused")


@pytest.fixture
def no_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    # The SDK also finds credentials in ANTHROPIC_PROFILE, workload identity variables
    # and a profile saved under ~/.config/anthropic. Hide all of them, or a developer's
    # real credentials would let the test send a real request.
    for name in [n for n in os.environ if n.startswith("ANTHROPIC_")]:
        monkeypatch.delenv(name)
    monkeypatch.setenv("HOME", str(tmp_path))
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


# ---- the tool loop, with a fake client (#95) ----

LOOP_SETTINGS = Settings(
    database_url="postgresql://unused", valkey_url="redis://unused", max_agent_turns=3
)
ANSWER_JSON = json.dumps(
    {"answer": "2 bedrooms", "value": 2, "unit": "count", "confidence": "high", "caveats": "",
     "citations": [{"element_id": "e1", "page_id": None, "bbox": None, "note": "MH1"}]}
)  # fmt: skip


def _tool_turn(call_id: str) -> SimpleNamespace:
    block = SimpleNamespace(type="tool_use", id=call_id, name="find_elements", input={})
    usage = SimpleNamespace(input_tokens=100, output_tokens=10)
    return SimpleNamespace(content=[block], stop_reason="tool_use", usage=usage)


def _answer_turn() -> SimpleNamespace:
    block = SimpleNamespace(type="text", text=ANSWER_JSON)
    usage = SimpleNamespace(input_tokens=100, output_tokens=10)
    return SimpleNamespace(content=[block], stop_reason="end_turn", usage=usage)


class FakeClaude:
    api_key = "test-key"
    auth_token = None
    credentials = None

    def __init__(self) -> None:
        self.responses: list[SimpleNamespace] = []
        self.requests: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(copy.deepcopy(kwargs))
        return self.responses.pop(0)


@pytest.fixture
def claude(monkeypatch: pytest.MonkeyPatch) -> FakeClaude:
    client = FakeClaude()
    monkeypatch.setattr(agent, "_client", lambda: client)
    monkeypatch.setattr(agent, "run_tool", lambda name, raw, ctx: '[{"id": "e1"}]')
    return client


def _loop() -> list[dict[str, Any]]:
    ctx = ToolContext(db=None, scope=[])  # type: ignore[arg-type]  # run_tool is faked
    return list(run_agent("How many bedrooms?", [], ctx, LOOP_SETTINGS))


def test_the_last_turn_takes_no_tool_calls_and_asks_for_the_answer(claude: FakeClaude) -> None:
    # max_agent_turns is 3: two tool turns, then the model has to answer.
    claude.responses = [_tool_turn("t1"), _tool_turn("t2"), _answer_turn()]
    events = _loop()
    assert [e["type"] for e in events] == ["step", "step", "final"]
    assert events[-1]["answer"].value == 2
    assert [r["tool_choice"] for r in claude.requests] == [
        {"type": "auto"},
        {"type": "auto"},
        {"type": "none"},
    ]
    # The note is a text block after the tool results, in the same user turn.
    last_user = claude.requests[2]["messages"][-1]
    assert last_user["role"] == "user"
    assert [b["type"] for b in last_user["content"]] == ["tool_result", "text"]
    assert last_user["content"][-1]["text"] == LAST_STEP_NOTE
    # Earlier turns carry only tool results.
    assert [b["type"] for b in claude.requests[1]["messages"][-1]["content"]] == ["tool_result"]


def test_the_question_states_the_step_budget(claude: FakeClaude) -> None:
    claude.responses = [_answer_turn()]
    _loop()
    # max_agent_turns is 3, and the last turn is the answer: 2 rounds of tool calls.
    assert "at most 2 rounds of tool calls" in claude.requests[0]["messages"][0]["content"]


def test_claude_request_omits_unused_filters_instead_of_compiling_nullable_unions(
    claude: FakeClaude,
) -> None:
    claude.responses = [_answer_turn()]
    _loop()
    tools = {tool["name"]: tool for tool in claude.requests[0]["tools"]}
    find = tools["find_elements"]["input_schema"]
    assert find["required"] == []
    assert find["properties"]["document_id"] == {"type": "string"}
    assert tools["count_elements"]["input_schema"]["required"] == ["kind"]


def test_step_limit_when_the_last_turn_still_gives_no_answer(claude: FakeClaude) -> None:
    claude.responses = [_tool_turn("t1"), _tool_turn("t2"), _tool_turn("t3")]
    with pytest.raises(AgentError) as raised:
        _loop()
    assert raised.value.code == "too_many_steps"
