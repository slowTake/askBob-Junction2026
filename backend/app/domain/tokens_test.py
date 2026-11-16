from app.domain.tokens import Word, classify, merge_split_numbers, room_candidates


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


def test_classify_swiss_labels() -> None:
    stanza = classify("Stanza")
    assert (stanza.kind, stanza.label, stanza.name) == ("room", "Stanza", "room (Stanza)")
    assert classify("2.01").kind == "room_number"
    assert classify("U1.05").kind == "room_number"
    assert classify("Whg. A").kind == "unit"
    assert classify("Whg. A").label == "A"
    assert classify("15.61 m²").properties == {"area_m2": 15.61}


def test_classify_height_and_decimal_comma_dimension() -> None:
    # colorful-34: "h1600" is a ceiling height of 1600 mm, "5,341" a 5341 mm dimension.
    height = classify("h1600")
    assert (height.kind, height.label, height.value_mm) == ("height", "h1600", 1600)
    assert classify("h746-").label == "h746"  # the stray stroke isn't part of the label
    dimension = classify("5,341")
    assert (dimension.kind, dimension.value_mm) == ("dimension", 5341)


def test_classify_finnish_names_and_numbered_codes() -> None:
    kitchen = classify("keittiö")
    assert (kitchen.kind, kitchen.name) == ("room", "kitchen (keittiö)")
    assert classify("Pukuh").properties["category"] == "dressing room"
    mh1 = classify("MH1")
    assert (mh1.kind, mh1.label, mh1.name) == ("room", "MH1", "bedroom (MH1)")
    # Not `number`: that is a plan-wide room number, and numbered rooms make up net area.
    assert mh1.properties == {"local_name": "makuuhuone", "code_number": "1"}
    assert classify("KPH").name == "bathroom (KPH)"


def test_classify_fuzzy_only_when_asked() -> None:
    assert classify("keitlio").kind == "text"
    fuzzy = classify("keitlio", fuzzy=True)
    assert (fuzzy.kind, fuzzy.label) == ("room", "keitlio")  # the drawing's text is kept
    assert fuzzy.properties["category"] == "kitchen"
    assert fuzzy.properties["fuzzy_match"] is True  # a doubtful reading (#133)


def test_repeated_unknown_words_are_room_candidates() -> None:
    # Issue #36: a word the vocabulary doesn't know, printed twice or more, may be a room
    # name in another language ("Slaapkamer", Dutch bedroom), so it is kept as a candidate.
    texts = ["Slaapkamer", "slaapkamer", "Badkamer", "MH", "MH", "h1600", "h1600", "yw", "yw"]
    # Badkamer appears once; MH is a known code; h1600 is a height; "yw" has two letters.
    assert room_candidates(texts) == {"slaapkamer"}


def test_room_candidates_need_letters_only() -> None:
    texts = ["A-A", "A-A", "3H+K", "3H+K", "NOTE 1", "NOTE 1", "työh.", "työh."]
    assert room_candidates(texts) == set()  # työh. is known; the others aren't word-like
