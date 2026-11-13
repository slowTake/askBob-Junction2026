from eval.scoring import is_correct, numbers_in


def test_numbers_in_handles_thousand_spaces_and_decimal_commas() -> None:
    assert numbers_in("door 900 mm, wall 10 800 mm, area 12,5 m²") == [900, 10800, 12.5]


def test_numeric_match_within_two_percent() -> None:
    # 2 % of 900 is 18, so 915 matches and 920 does not.
    assert is_correct("900", "The door is 915 mm wide.")
    assert not is_correct("900", "The door is 920 mm wide.")


def test_text_match_is_case_insensitive() -> None:
    assert is_correct("sauna", "It is next to the Sauna.")
    assert not is_correct("sauna", "It is next to the bathroom.")
