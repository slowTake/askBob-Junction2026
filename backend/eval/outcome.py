"""Turn one question's reply from /api/ask into an eval result. Pure.

`reply` is the data of the `answer` or `error` event; `stats` is the data of the closing
`done` event (model, tokens, steps, latency; empty from an API older than #98).
"""

from collections.abc import Mapping
from typing import Any

from eval.prices import Price, cost_usd
from eval.report import Result
from eval.scoring import score


def outcome(
    row: Mapping[str, Any],
    reply: Mapping[str, Any],
    stats: Mapping[str, Any],
    prices: Mapping[str, Price],
) -> Result:
    answered = "answer" in reply
    model = stats.get("model")
    return Result(
        source=row["source"],
        type=row["type"],
        correct=score(row["type"], row["expected"], reply.get("value")),
        verified=bool(reply.get("verified")),
        tokens_in=sum(
            stats.get(key, 0) for key in ("input_tokens", "cache_read_tokens", "cache_write_tokens")
        ),
        tokens_out=stats.get("output_tokens", 0),
        steps=stats.get("steps", 0),
        seconds=stats.get("latency_ms", 0) / 1000,
        cost_usd=cost_usd(stats, prices.get(model)) if model else None,
        cached=bool(stats.get("cached") or reply.get("cached")),
        error=None if answered else str(reply.get("code") or "no_answer"),
    )
