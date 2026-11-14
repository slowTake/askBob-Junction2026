import pytest

from eval.outcome import outcome
from eval.prices import Price

ROW = {"question": "How many doors?", "expected": 4, "type": "count", "source": "cubicasa5k"}
STATS = {
    "model": "m",
    "cached": False,
    "steps": 5,
    "latency_ms": 12_500,
    "input_tokens": 1_000,
    "output_tokens": 200,
    "cache_read_tokens": 9_000,
    "cache_write_tokens": 0,
    "requests": 3,
}
PRICES = {"m": Price(input=2.0, output=10.0, cache_read=0.2)}


def test_answer_is_scored_and_costed() -> None:
    reply = {"answer": "4 doors", "value": 4, "verified": True, "cached": False}
    result = outcome(ROW, reply, STATS, PRICES)
    assert (result.source, result.type, result.correct, result.verified) == (
        "cubicasa5k", "count", True, True,
    )  # fmt: skip
    assert result.tokens_in == 10_000  # 1,000 + 9,000 read from the cache
    assert result.tokens_out == 200
    assert (result.steps, result.seconds, result.cached, result.error) == (5, 12.5, False, None)
    # (1,000 x $2 + 200 x $10 + 9,000 x $0.20) / 1,000,000 = $0.0058
    assert result.cost_usd == pytest.approx(0.0058)


def test_error_reply_is_wrong_and_keeps_its_code_and_cost() -> None:
    reply = {"code": "too_many_steps", "message": "Could not find an answer."}
    result = outcome(ROW, reply, STATS, PRICES)
    assert (result.correct, result.verified, result.error) == (False, False, "too_many_steps")
    assert result.cost_usd == pytest.approx(0.0058)  # the failed run was paid for too


def test_unknown_model_has_no_cost() -> None:
    result = outcome(ROW, {"answer": "4", "value": 4, "verified": False}, STATS, {})
    assert result.cost_usd is None


def test_no_cost_when_a_fallback_model_answered_part_of_it() -> None:
    # The fallback model has its own price and we don't know which one ran.
    stats = {**STATS, "fallback_requests": 1}
    result = outcome(ROW, {"answer": "4", "value": 4, "verified": True}, stats, PRICES)
    assert result.cost_usd is None
    assert result.tokens_in == 10_000  # tokens are still reported


def test_a_backend_without_stats_still_scores() -> None:
    # An API from before #98 sends an empty `done` event.
    result = outcome(ROW, {"answer": "4", "value": 4, "verified": True, "cached": True}, {}, PRICES)
    assert (result.correct, result.cached, result.tokens_in, result.cost_usd) == (
        True, True, 0, None,
    )  # fmt: skip


def test_a_stream_that_ended_without_an_answer_is_an_error() -> None:
    result = outcome(ROW, {}, {}, PRICES)
    assert (result.correct, result.error) == (False, "no_answer")


def test_the_way_the_answer_was_produced_is_kept() -> None:
    reply = {"answer": "4 doors.", "value": 4, "verified": True}
    assert outcome(ROW, reply, {**STATS, "method": "server"}, PRICES).method == "server"
    assert outcome(ROW, reply, STATS, PRICES).method == "agent"  # an API from before #97
