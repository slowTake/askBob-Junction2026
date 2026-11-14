"""Summarise an eval run: accuracy and verified rate, overall and per source and type. Pure."""

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    source: str
    type: str
    correct: bool | None  # None: not scored automatically (text, other)
    verified: bool


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else "0%"


def _rates(results: list[Result]) -> tuple[str, str, int]:
    scored = [r for r in results if r.correct is not None]
    right = sum(bool(r.correct) for r in scored)
    verified = sum(r.verified for r in results)
    accuracy = f"{right}/{len(scored)} correct ({_pct(right, len(scored))})"
    verified_rate = f"verified {verified}/{len(results)} ({_pct(verified, len(results))})"
    return accuracy, verified_rate, len(results) - len(scored)


def summarize(results: list[Result]) -> list[str]:
    """One overall line, then one indented line per (source, type), sorted."""
    accuracy, verified, unscored = _rates(results)
    lines = [f"overall: {accuracy}, {verified}, not scored {unscored}"]
    groups: dict[tuple[str, str], list[Result]] = defaultdict(list)
    for r in results:
        groups[(r.source, r.type)].append(r)
    for (source, kind), group in sorted(groups.items()):
        accuracy, verified, unscored = _rates(group)
        if unscored == len(group):
            accuracy = "not scored"
        lines.append(f"  {source} / {kind}: {accuracy}, {verified}")
    return lines
