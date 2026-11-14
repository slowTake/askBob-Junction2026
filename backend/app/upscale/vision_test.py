"""The one vision call of Upscale, against fake SDK clients: no network, no keys."""

import base64
import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2 as httpx
import pytest

from app.config import Settings
from app.upscale import vision
from app.upscale.vision import ANSWER_SCHEMA, VisionError, find_missing, user_text

PNG = b"\x89PNG fake"
LISTED: list[dict[str, object]] = [{"kind": "door", "box": [1, 2, 3, 4]}]


def _settings(**over: Any) -> Settings:
    return Settings(database_url="postgresql://u@h/db", valkey_url="redis://h", **over)


class FakeMessages:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response, self.error = response, error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def _claude(
    monkeypatch: pytest.MonkeyPatch, text: str = '{"elements": []}', stop: str = "end_turn"
) -> FakeMessages:
    response = SimpleNamespace(
        stop_reason=stop,
        content=[
            SimpleNamespace(type="thinking", thinking=""),  # Haiku 5.5 may think first
            SimpleNamespace(type="text", text=text),
        ],
        usage=SimpleNamespace(input_tokens=3100, output_tokens=420),
    )
    messages = FakeMessages(response)
    client = SimpleNamespace(api_key="set", auth_token=None, credentials=None, messages=messages)
    monkeypatch.setattr(vision, "_anthropic_client", lambda timeout: client)
    return messages


def test_user_text_gives_the_image_size_and_what_is_known() -> None:
    text = user_text(1568, 1109, LISTED, omitted=0)
    assert "1568 x 1109" in text
    assert json.dumps(LISTED, separators=(",", ":")) in text
    assert "not listed" not in text
    assert "12 more" in user_text(1568, 1109, LISTED, omitted=12)


def test_claude_gets_one_image_the_schema_and_low_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _claude(monkeypatch, '{"elements": [{"kind": "door"}]}')
    seen = find_missing(PNG, 1568, 1109, LISTED, 0, _settings())

    [call] = messages.calls  # exactly one request per page
    assert call["model"] == "claude-haiku-5-5"  # the default; UPSCALE_MODEL overrides it
    assert call["output_config"] == {
        "effort": "low",
        "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
    }
    image, text = call["messages"][0]["content"]
    assert image["source"] == {
        "type": "base64",
        "media_type": "image/png",
        "data": base64.b64encode(PNG).decode(),
    }
    assert text == {"type": "text", "text": user_text(1568, 1109, LISTED, 0)}
    assert seen.data == {"elements": [{"kind": "door"}]}
    assert (seen.model, seen.input_tokens, seen.output_tokens) == ("claude-haiku-5-5", 3100, 420)


def test_the_model_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _claude(monkeypatch)
    find_missing(PNG, 10, 10, [], 0, _settings(upscale_model="claude-sonnet-5-5"))
    assert messages.calls[0]["model"] == "claude-sonnet-5-5"


@pytest.mark.parametrize(
    ("text", "stop", "code"),
    [
        ("not json", "end_turn", "upscale_failed"),
        ('{"elements": [', "max_tokens", "upscale_failed"),  # cut off mid-answer
        ("", "refusal", "refused"),
    ],
)
def test_an_unreadable_answer_is_an_error_code_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, text: str, stop: str, code: str
) -> None:
    _claude(monkeypatch, text, stop)
    with pytest.raises(VisionError) as raised:
        find_missing(PNG, 10, 10, [], 0, _settings())
    assert raised.value.code == code


def test_no_credentials_means_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SimpleNamespace(api_key=None, auth_token=None, credentials=None)
    monkeypatch.setattr(vision, "_anthropic_client", lambda timeout: client)
    with pytest.raises(VisionError) as raised:
        find_missing(PNG, 10, 10, [], 0, _settings())
    assert raised.value.code == "llm_not_configured"

    monkeypatch.delenv("VERDA_API_KEY", raising=False)
    with pytest.raises(VisionError) as raised:
        find_missing(PNG, 10, 10, [], 0, _settings(llm_provider="verda"))
    assert raised.value.code == "llm_not_configured"


def test_sdk_errors_become_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://api.invalid/v1/messages")
    busy = anthropic.RateLimitError(
        "slow down", response=httpx.Response(429, request=request), body=None
    )
    down = anthropic.APIConnectionError(request=request)
    for error, code in ((busy, "llm_busy"), (down, "llm_unavailable")):
        messages = FakeMessages(error=error)
        client = SimpleNamespace(
            api_key="set", auth_token=None, credentials=None, messages=messages
        )
        monkeypatch.setattr(vision, "_anthropic_client", lambda timeout, c=client: c)
        with pytest.raises(VisionError) as raised:
            find_missing(PNG, 10, 10, [], 0, _settings())
        assert raised.value.code == code


def test_verda_gets_the_image_as_a_data_url_and_the_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"elements": []}'))],
        usage=SimpleNamespace(prompt_tokens=2000, completion_tokens=100),
    )
    completions = FakeMessages(response)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setenv("VERDA_API_KEY", "test-key")
    monkeypatch.setattr(vision, "_verda_client", lambda base_url, key, timeout: client)

    seen = find_missing(PNG, 10, 10, [], 0, _settings(llm_provider="verda"))

    [call] = completions.calls
    assert call["model"] == "kimi-k3-1-pro"
    assert "tools" not in call  # tools with a response_format made Kimi invent ids (D-020)
    assert call["response_format"]["json_schema"]["schema"] == ANSWER_SCHEMA
    user = call["messages"][1]["content"]
    assert user[0] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64," + base64.b64encode(PNG).decode()},
    }
    assert (seen.data, seen.model, seen.input_tokens) == ({"elements": []}, "kimi-k3-1-pro", 2000)
