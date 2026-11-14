"""What a question cost: tokens times the model's price. Pure.

Prices are US dollars per million tokens. Correct them here when a provider changes
them, or pass `--price MODEL=IN,OUT[,CACHE_READ[,CACHE_WRITE]]` to `eval.run_eval`.
"""

from collections.abc import Mapping
from dataclasses import dataclass

MILLION = 1_000_000


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_read: float | None = None  # None: cached input costs the same as other input
    cache_write: float | None = None


# Anthropic list prices, checked 2026-11-03. A 5-minute cache write costs 1.25x input.
# A cache read costs 0.05x input on Opus and Sonnet 5.5 and 0.1x on Haiku 5.5.
# Haiku 5.5 costs $0.50 in, $2.50 out when one prompt is over 100,000 tokens. Usage is
# added up per question, not per prompt, so that rate is not applied here.
# Verda shows its prices only in the Console (Inference -> Models), so its models are
# not listed: pass them with --price, or add them here.
PRICES: dict[str, Price] = {
    "claude-opus-5-5": Price(4.0, 20.0, cache_read=0.2, cache_write=5.0),
    "claude-sonnet-5-5": Price(2.0, 10.0, cache_read=0.1, cache_write=2.5),
    "claude-haiku-5-5": Price(0.1, 0.5, cache_read=0.01, cache_write=0.125),
}


def cost_usd(usage: Mapping[str, int], price: Price | None) -> float | None:
    """Dollars for one question's usage, or None when the model's price is unknown."""
    if price is None:
        return None
    read = price.input if price.cache_read is None else price.cache_read
    write = price.input if price.cache_write is None else price.cache_write
    total = (
        usage.get("input_tokens", 0) * price.input
        + usage.get("output_tokens", 0) * price.output
        + usage.get("cache_read_tokens", 0) * read
        + usage.get("cache_write_tokens", 0) * write
    )
    return total / MILLION


def parse_price(text: str) -> tuple[str, Price]:
    """ "kimi-k3-1-pro=2,10" -> the model and its price. Raises ValueError otherwise."""
    model, _, numbers = text.partition("=")
    values = [float(part) for part in numbers.split(",")] if numbers else []
    if not model or not 2 <= len(values) <= 4:
        raise ValueError(f"expected MODEL=IN,OUT[,CACHE_READ[,CACHE_WRITE]], got {text!r}")
    return model, Price(*values)
