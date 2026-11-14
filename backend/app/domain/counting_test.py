from app.domain.counting import Countable, count

# A small IFC-like model: two storeys, doors and fixtures.
MODEL = [
    Countable("d1", "door", None, "1. Sal", None, None, None),
    Countable("d2", "door", None, "1. Sal", None, None, None),
    Countable("d3", "door", None, "3. Sal", None, None, None),
    Countable("w1", "window", None, "3. Sal", None, None, None),
    Countable("f1", "fixture", None, "1. Sal", "wc", None, None),
    Countable("f2", "fixture", None, "3. Sal", "bathtub", None, None),
    Countable("f3", "fixture", None, "3. Sal", "wc", None, None),
]

# A Swiss plan page: rooms with a printed label and a vocabulary category.
PLAN = [
    Countable("r1", "room", 0, None, None, "kitchen", "Küche"),
    Countable("r2", "room", 0, None, None, "kitchen", "Küche"),
    Countable("r3", "room", 0, None, None, "bedroom", "Zimmer"),
    Countable("r4", "room", 1, None, None, "balcony", "Balkon"),
    Countable("r5", "room", 1, None, None, "kitchen", "Wohnküche"),
]


def test_counts_every_element_of_the_kind() -> None:
    result = count(MODEL, kind="door")
    # d1, d2, d3
    assert result.total == 3
    assert [c.element_id for c in result.listed] == ["d1", "d2", "d3"]


def test_filters_by_storey() -> None:
    # Doors on '1. Sal': d1, d2. Storey names match ignoring case and outer spaces.
    assert count(MODEL, kind="door", storey="1. Sal").total == 2
    assert count(MODEL, kind="door", storey=" 1. sal ").total == 2
    assert count(MODEL, kind="door", storey="2. Sal").total == 0


def test_filters_fixtures_by_subtype() -> None:
    # WCs: f1 and f3, one per storey.
    result = count(MODEL, kind="fixture", subtype="wc")
    assert result.total == 2
    assert result.by_storey == {"1. Sal": 1, "3. Sal": 1}
    assert count(MODEL, kind="fixture", subtype="WC").total == 2


def test_name_is_an_exact_label_not_a_substring() -> None:
    # 'Küche' is r1 and r2; 'Wohnküche' (r5) contains it but is another label.
    assert count(PLAN, kind="room", name="Küche").total == 2
    assert count(PLAN, kind="room", name="küche").total == 2
    assert count(PLAN, kind="room", name="Wohnküche").total == 1


def test_name_ignores_runs_of_whitespace() -> None:
    rooms = [Countable("x", "room", 0, None, None, None, "Soggiorno /  pranzo")]
    assert count(rooms, kind="room", name="Soggiorno / pranzo").total == 1


def test_filters_rooms_by_category() -> None:
    # Category 'kitchen': r1, r2 and r5 (Wohnküche is a kitchen too).
    assert count(PLAN, kind="room", category="kitchen").total == 3
    assert count(PLAN, kind="room", category="balcony").total == 1


def test_filters_combine() -> None:
    # Kitchens on page 1 (index 1): only r5.
    assert count(PLAN, kind="room", category="kitchen", page_index=1).total == 1


def test_breaks_counts_down_by_page() -> None:
    result = count(PLAN, kind="room")
    # Page 0: r1, r2, r3; page 1: r4, r5.
    assert result.by_page == {("", 0): 3, ("", 1): 2}
    assert result.by_storey == {}


def test_total_stays_exact_when_the_list_is_capped() -> None:
    walls = [Countable(f"w{i}", "wall", None, "1", None, None, None) for i in range(846)]
    result = count(walls, kind="wall", list_max=50)
    # 846 is the dataset's answer for the Maleva model's walls.
    assert result.total == 846
    assert len(result.listed) == 50
    assert result.by_storey == {"1": 846}


def test_nothing_matches() -> None:
    result = count(MODEL, kind="stair")
    assert result.total == 0
    assert result.listed == []
    assert result.by_page == {}
    assert result.by_storey == {}


def test_elements_without_the_property_do_not_match_its_filter() -> None:
    # A door with no storey must not be counted on any storey.
    items = [Countable("d", "door", 0, None, None, None, None)]
    assert count(items, kind="door", storey="1. Sal").total == 0
    assert count(items, kind="door").total == 1


# An IFC model's spaces: the label is the room number, the name is IfcSpace.LongName.
SPACES = [
    Countable("s1", "room", None, "EG", None, None, "005", "Kitchen"),
    Countable("s2", "room", None, "1.OG", None, None, "105", "Kitchen"),
    Countable("s3", "room", None, "EG", None, None, "006", "Meeting room 1"),
]


def test_name_matches_an_ifc_space_by_its_name_or_its_number() -> None:
    # 'Kitchen' is s1 and s2, by name; '005' is s1, by label.
    assert count(SPACES, kind="room", name="Kitchen").total == 2
    assert count(SPACES, kind="room", name="kitchen", storey="EG").total == 1
    assert count(SPACES, kind="room", name="005").total == 1
    assert count(SPACES, kind="room", name="Meeting room").total == 0  # still exact


def test_an_element_whose_label_and_name_both_match_counts_once() -> None:
    rooms = [Countable("x", "room", 0, None, None, None, "Küche", "Küche")]
    assert count(rooms, kind="room", name="Küche").total == 1


def test_pages_of_different_documents_are_counted_apart() -> None:
    # Page 0 of document A: a1, a2; page 0 of document B: b1. Never one "page 0" of 3.
    rooms = [
        Countable("a1", "room", 0, None, None, None, None, None, "doc-a"),
        Countable("b1", "room", 0, None, None, None, None, None, "doc-b"),
        Countable("a2", "room", 0, None, None, None, None, None, "doc-a"),
    ]
    result = count(rooms, kind="room")
    assert result.total == 3
    assert result.by_page == {("doc-a", 0): 2, ("doc-b", 0): 1}


def test_listing_order_does_not_depend_on_the_input_order() -> None:
    # Document, then page (elements without a page last), then id.
    items = [
        Countable("e", "door", None, None, None, None, None, None, "doc-a"),
        Countable("d", "door", 0, None, None, None, None, None, "doc-b"),
        Countable("c", "door", 1, None, None, None, None, None, "doc-a"),
        Countable("b", "door", 0, None, None, None, None, None, "doc-a"),
        Countable("a", "door", 0, None, None, None, None, None, "doc-a"),
    ]
    expected = ["a", "b", "c", "e", "d"]
    assert [c.element_id for c in count(items, kind="door").listed] == expected
    assert [c.element_id for c in count(items[::-1], kind="door").listed] == expected
    # The cap keeps the first of that order: a, b.
    assert [c.element_id for c in count(items, kind="door", list_max=2).listed] == ["a", "b"]
