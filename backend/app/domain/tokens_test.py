from app.domain.tokens import Word, classify, merge_split_numbers


def test_merge_thousands_split() -> None:
    words = [Word((0, 0, 10, 10), "10"), Word((14, 0, 32, 10), "800")]
    merged = merge_split_numbers(words)
    assert [w.text for w in merged] == ["10 800"]
    assert merged[0].bbox == (0, 0, 32, 10)


def test_no_merge_across_big_gap_or_other_line() -> None:
    far = [Word((0, 0, 10, 10), "10"), Word((40, 0, 58, 10), "800")]
    other_line = [Word((0, 0, 10, 10), "10"), Word((12, 30, 30, 40), "800")]
    assert len(merge_split_numbers(far)) == 2
    assert len(merge_split_numbers(other_line)) == 2


def test_classify_room() -> None:
    c = classify("MH")
    assert (c.kind, c.label, c.name) == ("room", "MH", "bedroom (MH)")


def test_classify_door_dimension_scale_area() -> None:
    assert classify("09").kind == "door"
    assert classify("09").value_mm == 900
    assert classify("10 800").value_mm == 10800
    assert classify("1:50").properties == {"denominator": 50}
    assert classify("80M2").properties == {"area_m2": 80.0}


def test_classify_falls_back_to_text() -> None:
    assert classify("3H+K").kind == "text"
