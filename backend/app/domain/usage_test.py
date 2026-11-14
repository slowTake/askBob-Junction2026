from app.domain.usage import Usage


def test_adds_up_requests() -> None:
    usage = Usage()
    usage.add(input_tokens=100, output_tokens=10)
    usage.add(input_tokens=20, output_tokens=5, cache_read_tokens=100, cache_write_tokens=30)
    assert usage.as_dict() == {
        "input_tokens": 120,  # 100 + 20
        "output_tokens": 15,  # 10 + 5
        "cache_read_tokens": 100,
        "cache_write_tokens": 30,
        "requests": 2,
    }


def test_total_input_counts_cached_tokens_too() -> None:
    usage = Usage(input_tokens=20, cache_read_tokens=100, cache_write_tokens=30)
    assert usage.total_input_tokens == 150  # 20 + 100 + 30


def test_a_new_usage_is_empty() -> None:
    assert Usage().as_dict() == {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "requests": 0,
    }
