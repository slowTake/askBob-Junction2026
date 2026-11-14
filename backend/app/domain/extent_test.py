from app.domain.extent import element_extent

LABEL = (500.0, 390.0, 539.0, 424.0)
SQUARE = [[400, 300], [700, 300], [700, 500], [400, 500]]


def test_room_with_outline_is_highlighted_as_the_room() -> None:
    extent = element_extent("room", LABEL, {"polygon_px": SQUARE})
    # Bounds of the outline by hand: x 400..700, y 300..500.
    assert extent.bbox == (400, 300, 700, 500)
    assert extent.polygon == ((400, 300), (700, 300), (700, 500), (400, 500))
    assert extent.target == "element"


def test_room_without_outline_falls_back_to_its_label() -> None:
    extent = element_extent("room", LABEL, {"region": "not_closed"})
    assert extent.bbox == LABEL
    assert extent.polygon is None
    assert extent.target == "label"


def test_too_few_points_or_junk_is_not_an_outline() -> None:
    assert element_extent("room", LABEL, {"polygon_px": [[1, 2], [3, 4]]}).target == "label"
    assert element_extent("room", LABEL, {"polygon_px": "oops"}).target == "label"
    assert element_extent("room", LABEL, {"polygon_px": [[1, 2], [3], [5, 6]]}).target == "label"


def test_walls_and_doors_are_their_own_box() -> None:
    # A wall's bbox is the wall itself, not a name standing for it.
    extent = element_extent("wall", (0, 0, 10, 200), {})
    assert extent.bbox == (0, 0, 10, 200)
    assert extent.polygon is None
    assert extent.target == "element"


def test_room_without_any_box_is_not_a_label() -> None:
    # An IFC space not drawn on a storey plan: located in 3D by its GlobalId, not by a name.
    extent = element_extent("room", None, {})
    assert extent.bbox is None
    assert extent.target == "element"


def test_booleans_and_flat_outlines_are_not_outlines() -> None:
    assert element_extent("room", LABEL, {"polygon_px": [[True, 0], [1, 0], [1, 1]]}).target == (
        "label"
    )
    # Three points on one line: zero area, nothing to highlight.
    assert element_extent("room", LABEL, {"polygon_px": [[0, 0], [5, 0], [10, 0]]}).target == (
        "label"
    )
