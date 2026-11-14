from app.domain.labels import Label, is_numbering_scheme, link_room_labels, unnumbered_are_legend


def test_stacked_name_number_area() -> None:
    # Swiss PDF layout: name, number and area centred under each other, 10 px lines.
    labels = [
        Label("room", (100, 100, 140, 110)),  # Zimmer
        Label("room_number", (110, 112, 130, 122)),  # 2.01
        Label("area", (105, 124, 135, 134)),  # 15.61 m²
    ]
    assert link_room_labels(labels) == {0: {"room_number": 1, "area": 2}}


def test_each_number_is_used_once_and_far_labels_are_ignored() -> None:
    labels = [
        Label("room", (100, 100, 140, 110)),
        Label("room", (100, 200, 140, 210)),
        Label("room_number", (110, 212, 130, 222)),  # belongs to the second room
        Label("room_number", (400, 112, 420, 122)),  # far to the right of the first
    ]
    assert link_room_labels(labels) == {1: {"room_number": 2}}


def test_label_above_is_not_linked() -> None:
    labels = [Label("room", (100, 100, 140, 110)), Label("area", (105, 80, 135, 90))]
    assert link_room_labels(labels) == {}


def test_unnumbered_names_are_legend_when_the_plan_numbers_its_rooms() -> None:
    # site1000: 25 numbered rooms, plus "WC" and "Dusche" in the legend box.
    assert unnumbered_are_legend(numbered=25, unnumbered=2)
    # A plan without room numbers (e.g. Finnish real-estate plans): names are rooms.
    assert not unnumbered_are_legend(numbered=0, unnumbered=6)
    assert not unnumbered_are_legend(numbered=2, unnumbered=1)  # too few to tell


def test_room_numbers_of_one_plan_share_their_floor_prefix() -> None:
    # Swiss plan: 1.01, 1.07, 1.17, U1.05 are rooms of floor 1.
    assert is_numbering_scheme(["1.01", "1.07", "1.17", "U1.05"])


def test_metre_dimensions_are_not_a_numbering_scheme() -> None:
    # PR #65 review: "3.20", "4.10", "2.75" under Nordic room names are dimensions.
    assert not is_numbering_scheme(["3.20", "4.10", "2.75"])


def test_too_few_numbers_are_not_a_scheme() -> None:
    assert not is_numbering_scheme(["1.01", "1.02"])
