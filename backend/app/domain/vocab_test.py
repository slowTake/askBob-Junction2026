from app.domain.vocab import door_width_mm, lookup_code


def test_room_code_lookup() -> None:
    code = lookup_code("MH")
    assert code is not None
    assert code.kind == "room"
    assert code.english == "bedroom"


def test_lookup_tolerates_case_space_and_dot() -> None:
    code = lookup_code(" kh. ")
    assert code is not None
    assert code.local_name == "kylpyhuone"


def test_fixture_code_with_dash() -> None:
    code = lookup_code("PK-V")
    assert code is not None
    assert code.kind == "fixture"


def test_unknown_code() -> None:
    assert lookup_code("XYZ") is None


def test_door_tag_modules() -> None:
    # Finnish door tags are widths in 100 mm modules: 08 -> 800 mm, 09 -> 900 mm.
    assert door_width_mm("08") == 800
    assert door_width_mm("09") == 900
    assert door_width_mm("10") == 1000


def test_door_tag_rejects_other_numbers() -> None:
    assert door_width_mm("9") is None  # not zero-padded: likely a grid label
    assert door_width_mm("3600") is None
    assert door_width_mm("13") is None
