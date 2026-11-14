import pytest

from eval.prices import PRICES, Price, cost_usd, parse_price

USAGE = {
    "input_tokens": 1_000_000,
    "output_tokens": 100_000,
    "cache_read_tokens": 2_000_000,
    "cache_write_tokens": 500_000,
}


def test_cost_adds_the_four_kinds_of_token() -> None:
    price = Price(input=4.0, output=20.0, cache_read=0.2, cache_write=5.0)
    # 1 M x $4 + 0.1 M x $20 + 2 M x $0.20 + 0.5 M x $5 = 4 + 2 + 0.4 + 2.5
    assert cost_usd(USAGE, price) == pytest.approx(8.9)


def test_cache_prices_default_to_the_input_price() -> None:
    price = Price(input=2.0, output=10.0)
    # (1 M + 2 M + 0.5 M) x $2 + 0.1 M x $10 = 7 + 1
    assert cost_usd(USAGE, price) == pytest.approx(8.0)


def test_unknown_price_gives_no_cost() -> None:
    assert cost_usd(USAGE, None) is None


def test_missing_token_counts_are_zero() -> None:
    assert cost_usd({"input_tokens": 500_000}, Price(input=4.0, output=20.0)) == pytest.approx(2.0)


def test_claude_opus_price_is_listed() -> None:
    # Anthropic list price on 2026-11-03: $4 in, $20 out, $0.20 cache read per million.
    assert PRICES["claude-opus-5-5"] == Price(4.0, 20.0, cache_read=0.2, cache_write=5.0)


def test_claude_haiku_price_has_cache_prices() -> None:
    # Anthropic list price: $0.10 in, $0.50 out. Cache reads are 0.1x input ($0.01) and
    # 5-minute cache writes 1.25x input ($0.125).
    assert PRICES["claude-haiku-5-5"] == Price(0.1, 0.5, cache_read=0.01, cache_write=0.125)


def test_parse_price_reads_model_and_prices() -> None:
    assert parse_price("kimi-k3-1-pro=2,10") == ("kimi-k3-1-pro", Price(2.0, 10.0))
    assert parse_price("m=2,10,0.2") == ("m", Price(2.0, 10.0, cache_read=0.2))


@pytest.mark.parametrize("text", ["kimi", "kimi=2", "kimi=a,b", "=2,10", "m=1,2,3,4,5"])
def test_parse_price_rejects_other_shapes(text: str) -> None:
    with pytest.raises(ValueError):
        parse_price(text)
