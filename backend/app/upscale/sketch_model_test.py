"""The sketch redraw's model call, against a fake SDK client: no network, no keys."""

import base64
import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2 as httpx
import pytest

from app.config import Settings
from app.upscale import sketch_model
from app.upscale.sketch_model import PLAN_SCHEMA, SketchAsk, ask_sketch
from app.upscale.vision import VisionError

PHOTO = b"\x89PNG photo"
DRAFT = b"\x89PNG draft"
EMPTY = '{"matches": false, "walls": [], "doors": [], "windows": [], "rooms": [], "texts": []}'


def _settings(**over: Any) -> Settings:
    return Settings(database_url="postgresql://u@h/db", valkey_url="redis://h", **over)


class FakeStream:
    def __init__(self, response: Any) -> None:
        self.response = response

    def __enter__(self) -> "FakeStream":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get_final_message(self) -> Any:
        return self.response


class FakeMessages:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response, self.error = response, error
        self.calls: list[dict[str, Any]] = []

    def stream(self, **kwargs: Any) -> FakeStream:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return FakeStream(self.response)


def _claude(
    monkeypatch: pytest.MonkeyPatch,
    text: str = EMPTY,
    stop: str = "end_turn",
    error: Exception | None = None,
    key: str | None = "set",
) -> FakeMessages:
    response = SimpleNamespace(
        stop_reason=stop,
        model="claude-opus-5-5",
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
        usage=SimpleNamespace(
            input_tokens=900, cache_creation_input_tokens=5000, cache_read_input_tokens=0,
            output_tokens=2400,
        ),
    )  # fmt: skip
    messages = FakeMessages(response, error)
    client = SimpleNamespace(
        api_key=key, auth_token=None, credentials=None, beta=SimpleNamespace(messages=messages)
    )
    monkeypatch.setattr(sketch_model, "_client", lambda timeout: client)
    return messages


def _images(call: dict[str, Any]) -> list[dict[str, Any]]:
    return [b for b in call["messages"][0]["content"] if b["type"] == "image"]


def test_the_first_round_sends_the_photo_and_asks_for_the_whole_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _claude(monkeypatch)
    look = ask_sketch(SketchAsk(PHOTO, 2576, 2000), _settings())

    [call] = messages.calls
    assert call["model"] == "claude-opus-5-5"  # SKETCH_MODEL's default
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {
        "effort": "high",
        "format": {"type": "json_schema", "schema": PLAN_SCHEMA},
    }
    # A declined request is retried on Anthropic's recommended fallback model.
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    [photo] = _images(call)
    assert base64.b64decode(photo["source"]["data"]) == PHOTO
    # The photo is the same in every round: cached after the first.
    assert photo["cache_control"] == {"type": "ephemeral"}
    text = " ".join(b["text"] for b in call["messages"][0]["content"] if b["type"] == "text")
    assert "2576 x 2000" in text and "draft" not in text
    # Tokens: plain input plus cache writes and reads (900 + 5000 + 0).
    assert (look.model, look.input_tokens, look.output_tokens) == ("claude-opus-5-5", 5900, 2400)
    assert look.data == json.loads(EMPTY)


def test_a_check_round_sends_the_draft_render_and_its_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _claude(monkeypatch)
    draft = {"walls": [{"x0": 1, "y0": 2, "x1": 3, "y1": 4, "outer": True}]}
    ask_sketch(SketchAsk(PHOTO, 100, 80, draft_png=DRAFT, draft=draft), _settings())

    [call] = messages.calls
    photo, render = _images(call)
    assert base64.b64decode(photo["source"]["data"]) == PHOTO
    assert base64.b64decode(render["source"]["data"]) == DRAFT
    assert "cache_control" not in render  # it changes every round
    text = " ".join(b["text"] for b in call["messages"][0]["content"] if b["type"] == "text")
    assert json.dumps(draft, separators=(",", ":")) in text


def test_settings_choose_the_model_and_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _claude(monkeypatch)
    ask_sketch(SketchAsk(PHOTO, 10, 10), _settings(sketch_model="m", sketch_effort="xhigh"))
    assert messages.calls[0]["model"] == "m"
    assert messages.calls[0]["output_config"]["effort"] == "xhigh"


@pytest.mark.parametrize(
    ("stop", "text", "code"),
    [
        ("refusal", EMPTY, "refused"),
        ("max_tokens", '{"walls": [', "sketch_failed"),  # cut off
        ("end_turn", "not json", "sketch_failed"),
    ],
)
def test_an_unusable_answer_is_a_vision_error(
    monkeypatch: pytest.MonkeyPatch, stop: str, text: str, code: str
) -> None:
    _claude(monkeypatch, text=text, stop=stop)
    with pytest.raises(VisionError) as caught:
        ask_sketch(SketchAsk(PHOTO, 10, 10), _settings())
    assert caught.value.code == code


def _status(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("x", response=httpx.Response(status, request=request), body=None)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (_status(anthropic.AuthenticationError, 401), "llm_not_configured"),
        (_status(anthropic.RateLimitError, 429), "llm_busy"),
        (_status(anthropic.InternalServerError, 500), "llm_unavailable"),
        (
            anthropic.APITimeoutError(httpx.Request("POST", "https://api.anthropic.com")),
            "llm_unavailable",
        ),
    ],
)
def test_sdk_errors_become_codes_and_never_leak(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str
) -> None:
    _claude(monkeypatch, error=error)
    with pytest.raises(VisionError) as caught:
        ask_sketch(SketchAsk(PHOTO, 10, 10), _settings())
    assert caught.value.code == code


def test_no_credentials_means_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _claude(monkeypatch, key=None)
    with pytest.raises(VisionError) as caught:
        ask_sketch(SketchAsk(PHOTO, 10, 10), _settings())
    assert caught.value.code == "llm_not_configured" and messages.calls == []


def test_the_verda_provider_says_so_instead_of_falling_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _claude(monkeypatch)
    with pytest.raises(VisionError) as caught:
        ask_sketch(SketchAsk(PHOTO, 10, 10), _settings(llm_provider="verda"))
    assert caught.value.code == "sketch_needs_claude" and messages.calls == []


def test_the_schema_holds_the_whole_plan_and_a_verdict() -> None:
    assert PLAN_SCHEMA["required"] == ["matches", "walls", "doors", "windows", "rooms", "texts"]
    assert PLAN_SCHEMA["additionalProperties"] is False


def test_the_measured_ink_box_is_told_to_the_model_in_every_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _claude(monkeypatch)
    ink = (254, 272, 2314, 2277)
    ask_sketch(SketchAsk(PHOTO, 2576, 2576, ink=ink), _settings())
    ask_sketch(SketchAsk(PHOTO, 2576, 2576, DRAFT, {"walls": []}, ink=ink), _settings())

    for call in messages.calls:
        text = " ".join(b["text"] for b in call["messages"][0]["content"] if b["type"] == "text")
        assert "x 254 to 2314" in text and "y 272 to 2277" in text


def test_without_an_ink_box_nothing_is_said_about_it(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _claude(monkeypatch)
    ask_sketch(SketchAsk(PHOTO, 2576, 2000), _settings())
    [call] = messages.calls
    text = " ".join(b["text"] for b in call["messages"][0]["content"] if b["type"] == "text")
    assert "ink" not in text


def test_a_check_round_says_the_draft_is_drawn_in_red_over_the_sketch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _claude(monkeypatch)
    ask_sketch(SketchAsk(PHOTO, 100, 80, draft_png=DRAFT, draft={"walls": []}), _settings())
    [call] = messages.calls
    text = " ".join(b["text"] for b in call["messages"][0]["content"] if b["type"] == "text")
    assert "in red" in text
