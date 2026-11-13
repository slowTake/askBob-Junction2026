from app.domain.text import clip


def test_short_text_is_unchanged() -> None:
    assert clip("MH", 256) == "MH"


def test_text_at_the_limit_is_unchanged() -> None:
    assert clip("abcde", 5) == "abcde"  # exactly 5 characters fit in 5


def test_long_text_is_cut_to_the_limit_and_marked() -> None:
    # limit 5: four characters kept plus the ellipsis = 5 characters in total
    assert clip("abcdefgh", 5) == "abcd…"


def test_none_stays_none() -> None:
    assert clip(None, 5) is None


def test_limit_of_one_keeps_only_the_mark() -> None:
    assert clip("abc", 1) == "…"
