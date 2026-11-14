from app.domain.vocab import door_width_mm, lookup_code, lookup_room_name, unit_label


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


def test_room_names_in_swiss_languages() -> None:
    # Labels taken from data/swiss_dwellings/*.dxf (ROOM_TEXT layer).
    assert lookup_room_name("Stanza") == ("room", False)
    assert lookup_room_name("Chambre à coucher") == ("bedroom", False)
    assert lookup_room_name("wohnen/essen") == ("living room", False)
    assert lookup_room_name("Balkon") == ("balcony", True)  # outdoor
    assert lookup_room_name("Loggia") == ("loggia", True)
    assert lookup_room_name("Projekt: Site 1000") is None


def test_unit_labels() -> None:
    assert unit_label("App. A") == "A"
    assert unit_label("Whg. B") == "B"
    assert unit_label("Apartment 12") == "12"
    assert unit_label("Appartement") is None


def test_room_names_match_without_accents() -> None:
    # RapidOCR's recogniser has no accented letters: "Pièce" is read as "Piece" (D-024).
    assert lookup_room_name("Piece") == lookup_room_name("Pièce") == ("room", False)
    assert lookup_room_name("Kuche") == ("kitchen", False)
    assert lookup_room_name("Sejour/repas") == ("living room", False)
    assert lookup_room_name("Reduit") == ("storage", False)


def test_accent_folding_doesnt_invent_matches() -> None:
    assert lookup_room_name("Kuchen") is None
