from eval.scoring import score


def test_counts_must_be_exact() -> None:
    # Dataset README: "counts must be exact".
    assert score("count", 13, 13.0) is True
    assert score("count", 13, 12.0) is False
    assert score("count", 13, 13.2) is False


def test_measures_within_two_percent() -> None:
    # Dataset README: areas, lengths and volumes within 2%. 2% of 63.84 is 1.2768, so
    # 65.1 (off by 1.26) passes and 65.2 (off by 1.36) fails.
    assert score("area", 63.84, 65.1) is True
    assert score("area", 63.84, 65.2) is False
    # 2% of 185.129 is 3.70258: 181.5 (off by 3.629) passes, 181.4 (off by 3.729) fails.
    assert score("length", 185.129, 181.5) is True
    assert score("length", 185.129, 181.4) is False
    assert score("volume", 277.334, 277.334) is True


def test_a_missing_value_is_wrong() -> None:
    assert score("count", 2, None) is False
    assert score("area", 4.4, None) is False


def test_a_zero_measure_must_be_exact() -> None:
    # 2% of 0 is 0.
    assert score("area", 0, 0.0) is True
    assert score("area", 0, 0.01) is False


def test_text_and_other_are_not_scored() -> None:
    assert score("text", "Building Information: ...", None) is None
    assert score("other", 5, 5.0) is None
