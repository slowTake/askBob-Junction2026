from app.domain.vocab import (
    door_width_mm,
    lookup_code,
    lookup_room_name,
    room_code_number,
    unit_label,
)


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


def test_written_out_finnish_room_names() -> None:
    # Names written out on colorful-34 (eval/redraw_bench) and in the CubiCasa questions;
    # categories as the Swiss names and vision rooms use them (vocab.py, vision.py).
    assert lookup_room_name("keittiö") == ("kitchen", False)
    assert lookup_room_name("KEITTIO") == ("kitchen", False)  # OCR without ö
    assert lookup_room_name("aula") == ("corridor", False)  # a hall, as English "Hall"
    assert lookup_room_name("työhuone") == ("office", False)
    assert lookup_room_name("työh.") == ("office", False)  # its abbreviation on the plan
    assert lookup_room_name("tyoh") == ("office", False)
    assert lookup_room_name("kuisti") == ("porch", True)  # an unheated porch
    assert lookup_room_name("vaatehuone") == ("walk-in closet", False)
    assert lookup_room_name("varasto") == ("storage", False)
    assert lookup_room_name("pukuhuone") == ("dressing room", False)
    assert lookup_room_name("Pukuh") == ("dressing room", False)
    assert lookup_room_name("makuuhuone") == ("bedroom", False)
    assert lookup_room_name("olohuone") == ("living room", False)
    assert lookup_room_name("kylpyhuone") == ("bathroom", False)
    assert lookup_room_name("eteinen") == ("entrance hall", False)
    assert lookup_room_name("SAUNA") == ("sauna", False)
    assert lookup_room_name("PARVEKE") == ("balcony", True)  # outdoor


def test_german_and_english_names_from_the_issue() -> None:
    # Issue #36: words common in the dataset that must map to room kinds.
    assert lookup_room_name("Zimmer") == ("room", False)
    assert lookup_room_name("Küche") == ("kitchen", False)
    assert lookup_room_name("Korridor") == ("corridor", False)
    assert lookup_room_name("Wohnen/Essen") == ("living room", False)
    assert lookup_room_name("Reduit") == ("storage", False)
    assert lookup_room_name("Treppenhaus") == ("stairwell", False)
    assert lookup_room_name("Bedroom") == ("bedroom", False)
    assert lookup_room_name("Kitchen") == ("kitchen", False)
    assert lookup_room_name("Room") == ("room", False)


def test_bad_is_a_german_bathroom_not_only_a_code() -> None:
    # "Bad" is German for bathroom: the name wins over the Swedish code BAD (badrum).
    assert lookup_room_name("Bad") == ("bathroom", False)


def test_numbered_room_codes() -> None:
    # Issue #36 comment: "MH1"/"MH2" are bedroom 1 and 2; the number is the room number.
    code = lookup_code("MH1")
    assert code is not None
    assert (code.code, code.english) == ("MH", "bedroom")
    assert room_code_number("MH2") == ("MH", "2")
    assert room_code_number("MH") == ("MH", None)
    assert room_code_number("KPH") == ("KPH", None)
    assert room_code_number("JK1") is None  # numbers only follow room codes
    assert room_code_number("H1600") is None
    assert room_code_number("S1") is None  # one-letter codes: a section or grid mark


def test_kph_is_a_bathroom() -> None:
    code = lookup_code("KPH")
    assert code is not None
    assert (code.kind, code.local_name, code.english) == ("room", "kylpyhuone", "bathroom")


def test_one_edit_fuzzy_match_for_ocr() -> None:
    # One letter misread in a Finnish name of 6+ letters (after folding) still matches.
    assert lookup_room_name("keittio", fuzzy=True) == ("kitchen", False)
    assert lookup_room_name("keitlio", fuzzy=True) == ("kitchen", False)  # t -> l: one edit
    assert lookup_room_name("varast", fuzzy=True) == ("storage", False)  # one deletion
    assert lookup_room_name("vaasto", fuzzy=True) == ("storage", False)  # truth alternative
    assert lookup_room_name("kuistl", fuzzy=True) == ("porch", True)
    assert lookup_room_name("keitlio") is None  # exact unless the source is OCR


def test_fuzzy_match_does_not_invent_rooms() -> None:
    # "Veitlio" is how OCR read keittiö on colorful-34: two edits (k->V, t->l), too far.
    assert lookup_room_name("Veitlio", fuzzy=True) is None
    assert lookup_room_name("auta", fuzzy=True) is None  # "aula" has 4 letters: exact only
    assert lookup_room_name("sauma", fuzzy=True) is None  # a seam, not a sauna (5 letters)
    assert lookup_room_name("Kuchen", fuzzy=True) is None  # cake, not Küche
    assert lookup_room_name("Balken", fuzzy=True) is None  # a beam, not a Balkon
    assert lookup_room_name("h1600", fuzzy=True) is None
