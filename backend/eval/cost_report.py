"""Summarise what an eval run cost: tokens, tool calls, time and money per question. Pure.

Answers served from the answer cache made no model call, so they are counted apart and
left out of the averages.
"""

from collections import Counter, defaultdict

from eval.report import Result


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _left_out(cached: int) -> str:
    return f"{_plural(cached, 'cached answer')} left out" if cached else ""


def _line(results: list[Result]) -> str:
    asked = [r for r in results if not r.cached]
    left_out = _left_out(len(results) - len(asked))
    if not asked:
        return "no questions answered by the model" + (f" ({left_out})" if left_out else "")
    n = len(asked)
    usage = (
        f"{sum(r.tokens_in for r in asked) / n:,.0f} in + "
        f"{sum(r.tokens_out for r in asked) / n:,.0f} out tokens, "
        f"{sum(r.steps for r in asked) / n:.1f} steps, "
        f"{sum(r.seconds for r in asked) / n:.1f} s"
    )
    costs = [r.cost_usd for r in asked]
    if any(c is None for c in costs):
        notes = [_plural(n, "question"), left_out]
        return f"{usage}, price unknown ({'; '.join(x for x in notes if x)})"
    total = sum(c for c in costs if c is not None)
    notes = [f"{_plural(n, 'question')}, ${total:.2f} in total", left_out]
    return f"{usage}, ${total / n:.4f} per question ({'; '.join(x for x in notes if x)})"


def cost_lines(results: list[Result]) -> list[str]:
    """One overall line, then one indented line per (source, type), sorted."""
    lines = [f"cost overall: {_line(results)}"]
    groups: dict[tuple[str, str], list[Result]] = defaultdict(list)
    for r in results:
        groups[(r.source, r.type)].append(r)
    if len(groups) > 0 and any(not r.cached for r in results):
        for (source, kind), group in sorted(groups.items()):
            lines.append(f"  {source} / {kind}: {_line(group)}")
    return lines


def error_line(results: list[Result]) -> str:
    """How many questions got no answer, by the API's error code, most frequent first."""
    codes = Counter(r.error for r in results if r.error)
    if not codes:
        return "errors: none"
    listed = ", ".join(f"{code} {count}" for code, count in codes.most_common())
    return f"errors: {sum(codes.values())} of {_plural(len(results), 'question')} ({listed})"


def _correct(results: list[Result]) -> str:
    scored = [r for r in results if r.correct is not None]
    return f"{sum(bool(r.correct) for r in scored)} of {len(scored)} scored correct"


def method_line(results: list[Result]) -> str:
    """How many questions the server answered without the agent loop, and how each
    way of answering scored (#97)."""
    server = [r for r in results if r.method == "server"]
    agent = [r for r in results if r.method != "server"]
    share = f"{len(server) / len(results):.0%}" if results else "0%"
    return (
        f"without the agent: {len(server)} of {_plural(len(results), 'question')} ({share}), "
        f"{_correct(server)}; agent: {_correct(agent)}"
    )
