from eval.cost_report import cost_lines, error_line, method_line
from eval.report import Result


def _result(source: str = "cubicasa5k", kind: str = "count", **fields: object) -> Result:
    return Result(source, kind, correct=True, verified=True, **fields)  # type: ignore[arg-type]


def test_averages_and_total_per_group() -> None:
    results = [
        _result(tokens_in=10_000, tokens_out=500, steps=4, seconds=10.0, cost_usd=0.03),
        _result(tokens_in=30_000, tokens_out=1_500, steps=8, seconds=30.0, cost_usd=0.05),
        _result("ifc_models", "area", tokens_in=2_000, tokens_out=100, steps=1, seconds=2.0,
                cost_usd=0.01),
    ]  # fmt: skip
    lines = cost_lines(results)
    # Overall: (10,000 + 30,000 + 2,000) / 3 = 14,000 in; 2,100 / 3 = 700 out;
    # 13 / 3 = 4.3 steps; 42 / 3 = 14.0 s; $0.09 / 3 = $0.0300.
    assert lines[0] == (
        "cost overall: 14,000 in + 700 out tokens, 4.3 steps, 14.0 s, "
        "$0.0300 per question (3 questions, $0.09 in total)"
    )
    # cubicasa5k: 20,000 in; 1,000 out; 6.0 steps; 20.0 s; $0.08 / 2 = $0.0400.
    assert lines[1] == (
        "  cubicasa5k / count: 20,000 in + 1,000 out tokens, 6.0 steps, 20.0 s, "
        "$0.0400 per question (2 questions, $0.08 in total)"
    )
    assert lines[2].startswith("  ifc_models / area: 2,000 in + 100 out tokens, 1.0 steps, 2.0 s, ")


def test_cached_answers_are_left_out_and_counted() -> None:
    results = [
        _result(tokens_in=10_000, tokens_out=500, steps=4, seconds=10.0, cost_usd=0.03),
        _result(cached=True, seconds=0.1),
    ]
    lines = cost_lines(results)
    assert lines[0] == (
        "cost overall: 10,000 in + 500 out tokens, 4.0 steps, 10.0 s, "
        "$0.0300 per question (1 question, $0.03 in total; 1 cached answer left out)"
    )


def test_unknown_price_shows_no_cost() -> None:
    results = [_result(tokens_in=10_000, tokens_out=500, steps=4, seconds=10.0, cost_usd=None)]
    assert cost_lines(results)[0] == (
        "cost overall: 10,000 in + 500 out tokens, 4.0 steps, 10.0 s, price unknown (1 question)"
    )


def test_nothing_to_report_when_every_answer_was_cached_or_none_asked() -> None:
    assert cost_lines([]) == ["cost overall: no questions answered by the model"]
    assert cost_lines([_result(cached=True)]) == [
        "cost overall: no questions answered by the model (1 cached answer left out)"
    ]


def test_errors_are_counted_by_code() -> None:
    results = [
        _result(error="too_many_steps"),
        _result(error="llm_busy"),
        _result(error="too_many_steps"),
        _result(),
    ]
    assert error_line(results) == "errors: 3 of 4 questions (too_many_steps 2, llm_busy 1)"
    assert error_line([_result()]) == "errors: none"


def test_share_answered_without_the_agent_and_how_each_way_scored() -> None:
    results = [
        Result("a", "count", correct=True, verified=True, method="server"),
        Result("a", "count", correct=False, verified=True, method="server"),
        Result("a", "text", correct=None, verified=True, method="server"),
        Result("a", "count", correct=True, verified=True),
    ]
    # 3 of 4 by the server; of its 2 scored answers 1 is right; the agent's 1 is right.
    assert method_line(results) == (
        "without the agent: 3 of 4 questions (75%), 1 of 2 scored correct; "
        "agent: 1 of 1 scored correct"
    )
    assert method_line([]) == (
        "without the agent: 0 of 0 questions (0%), 0 of 0 scored correct; "
        "agent: 0 of 0 scored correct"
    )
