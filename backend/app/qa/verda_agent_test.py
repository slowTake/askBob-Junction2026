"""The Verda (Kimi) loop emits the same events as the Claude loop, with a fake client."""

import json
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import Settings
from app.qa import verda_agent
from app.qa.agent import AgentError, FinalAnswer
from app.qa.tools import ToolContext, ToolInputError
from app.qa.verda_agent import run_verda_agent

SETTINGS = Settings(
    database_url="postgresql://unused", valkey_url="redis://unused", max_agent_turns=3
)
ANSWER = {
    "answer": "2 bedrooms",
    "value": 2,
    "unit": None,
    "confidence": "high",
    "caveats": "",
    "citations": [{"element_id": "e1", "page_id": None, "bbox": None, "note": "MH1"}],
}


def _call(call_id: str, name: str, arguments: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id, type="function", function=SimpleNamespace(name=name, arguments=arguments)
    )


def _response(
    calls: list[SimpleNamespace], finish: str = "tool_calls", content: str | None = None
) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=calls or None)
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason=finish, message=message)],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10),
    )


class FakeClient:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.responses = responses
        self.requests: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeClient]:
    client = FakeClient([])
    monkeypatch.setenv("VERDA_API_KEY", "test-key")
    monkeypatch.setattr(verda_agent, "_client", lambda base_url, key: client)

    def run_tool(name: str, raw: Any, ctx: ToolContext) -> str:
        if raw.get("element_id") == "missing":
            raise ToolInputError("no such element in scope")
        return json.dumps([{"id": "e1", "kind": "room", "label": "MH1"}])

    monkeypatch.setattr(verda_agent, "run_tool", run_tool)
    yield client


def _events(question: str = "How many bedrooms?") -> list[dict[str, Any]]:
    ctx = ToolContext(db=None, scope=[])  # type: ignore[arg-type]  # run_tool is faked
    return list(run_verda_agent(question, [], ctx, SETTINGS))


def test_tool_step_then_final_answer(fake: FakeClient) -> None:
    fake.responses = [
        _response([_call("c1", "find_elements", '{"kind": "room", "text": null}')]),
        _response([_call("c2", "final_answer", json.dumps(ANSWER))]),
    ]
    events = _events()
    assert events == [
        {"type": "step", "tool": "find_elements", "input": {"kind": "room", "text": None}},
        {
            "type": "final",
            "answer": FinalAnswer.model_validate(ANSWER),
            # Two requests of 100 prompt + 10 completion tokens each.
            "usage": {"input_tokens": 200, "output_tokens": 20},
        },
    ]
    second = fake.requests[1]["messages"]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "tool"]
    assert second[3]["tool_call_id"] == "c1"


def test_every_request_requires_a_tool_call_and_offers_the_final_tool(fake: FakeClient) -> None:
    fake.responses = [_response([_call("c1", "final_answer", json.dumps(ANSWER))])]
    _events()
    request = fake.requests[0]
    assert request["model"] == "kimi-k3-1-pro"
    assert request["tool_choice"] == "required"
    assert "response_format" not in request  # Kimi skips tools when it is set (#51 probe)
    assert request["tools"][-1]["function"]["name"] == "final_answer"


def test_verda_model_env_picks_the_model_sent(
    fake: FakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # DeepSeek runs on the same loop, chosen with VERDA_MODEL alone (#86).
    monkeypatch.setenv("VERDA_MODEL", "deepseek-4-1-flash-1017")
    settings = Settings(database_url="postgresql://unused", valkey_url="redis://unused")
    fake.responses = [_response([_call("c1", "final_answer", json.dumps(ANSWER))])]
    ctx = ToolContext(db=None, scope=[])  # type: ignore[arg-type]  # run_tool is faked
    list(run_verda_agent("How many bedrooms?", [], ctx, settings))
    assert fake.requests[0]["model"] == "deepseek-4-1-flash-1017"


def test_bad_tool_input_goes_back_as_an_error_and_the_loop_continues(fake: FakeClient) -> None:
    fake.responses = [
        _response([_call("c1", "get_element", '{"element_id": "missing"}')]),
        _response([_call("c2", "get_element", "not json")]),
        _response([_call("c3", "final_answer", json.dumps(ANSWER))]),
    ]
    events = _events()
    assert [e["type"] for e in events] == ["step", "step", "final"]
    assert fake.requests[1]["messages"][-1]["content"] == "Error: no such element in scope"
    assert fake.requests[2]["messages"][-1]["content"] == "Error: arguments are not valid JSON"


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (_response([], finish="length"), "too_long"),
        (_response([], finish="content_filter"), "refused"),
        (_response([], finish="stop", content="Two bedrooms."), "bad_answer"),
        (_response([_call("c1", "final_answer", '{"answer": "2"}')]), "bad_answer"),
    ],
)
def test_unusable_responses_map_to_agent_errors(
    fake: FakeClient, response: SimpleNamespace, code: str
) -> None:
    fake.responses = [response]
    with pytest.raises(AgentError) as raised:
        _events()
    assert raised.value.code == code


def test_step_limit(fake: FakeClient) -> None:
    # SETTINGS.max_agent_turns is 3: three tool turns and no final answer.
    fake.responses = [_response([_call(f"c{i}", "find_elements", "{}")]) for i in range(3)]
    with pytest.raises(AgentError) as raised:
        _events()
    assert raised.value.code == "too_many_steps"


@pytest.mark.parametrize("value", [None, "", "  \n"])
def test_missing_key_is_reported_as_not_configured(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("VERDA_API_KEY", raising=False)
    else:
        # docker compose passes VERDA_API_KEY through even when it is set but empty.
        monkeypatch.setenv("VERDA_API_KEY", value)
    with pytest.raises(AgentError) as raised:
        _events()
    assert raised.value.code == "llm_not_configured"
