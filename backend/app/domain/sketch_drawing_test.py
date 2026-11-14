"""The drawn shapes of a sketch plan: walls with gaps, door swings, window lines, labels.

Page 1000 x 1000 px: outer walls are 1.2 % = 12 px thick, inner walls 0.7 % = 7 px,
room names 2.4 % = 24 px, other text 1.6 % = 16 px. Hand calculations next to each
assertion.
"""

import pytest

from app.domain.sketch import Door, Note, Plan, Room, Wall, Window
from app.domain.sketch_drawing import sketch_shapes

PAGE = 1000.0
WALL = Wall((100, 100), (500, 100), outer=True)


def _shapes(**parts: object) -> dict[str, list[dict[str, object]]]:
    found: dict[str, list[dict[str, object]]] = {}
    for s in sketch_shapes(Plan(**parts), PAGE, PAGE):  # type: ignore[arg-type]
        found.setdefault(s.kind, []).append({"text": s.text, "bbox": s.bbox, **s.properties})
    return found


def test_a_wall_is_a_filled_band_with_square_ends() -> None:
    [wall] = _shapes(walls=(WALL,))["wall"]
    # Half thickness 6: the band runs from x 94 to 506 and y 94 to 106.
    band = [[94, 106], [506, 106], [506, 94], [94, 94]]
    assert wall["polygon_px"] == band
    assert wall["pieces_px"] == [band]  # no openings: one piece
    assert wall["segment_px"] == [[100, 100], [500, 100]]
    assert wall["thickness"] == "outer" and wall["width_px"] == 12
    assert wall["bbox"] == (94, 94, 506, 106)
    assert wall["text"] is None


def test_an_inner_wall_is_thinner() -> None:
    [wall] = _shapes(walls=(Wall((100, 100), (100, 300), outer=False),))["wall"]
    # Half thickness 3.5, direction down (0, 1), normal (-1, 0).
    assert wall["polygon_px"] == [[96.5, 96.5], [96.5, 303.5], [103.5, 303.5], [103.5, 96.5]]
    assert wall["thickness"] == "inner" and wall["width_px"] == 7


def test_openings_leave_gaps_in_their_wall() -> None:
    shapes = _shapes(
        walls=(WALL,),
        doors=(Door((200, 100), (260, 100), hinge_at_a=True, toward=(230, 150)),),
        windows=(Window((300, 100), (380, 100)),),
    )
    [wall] = shapes["wall"]
    # Band 94..506 minus the door 200..260 and the window 300..380.
    assert wall["pieces_px"] == [
        [[94, 106], [200, 106], [200, 94], [94, 94]],
        [[260, 106], [300, 106], [300, 94], [260, 94]],
        [[380, 106], [506, 106], [506, 94], [380, 94]],
    ]


def test_a_door_is_a_leaf_and_a_quarter_circle_on_the_side_it_opens_to() -> None:
    [door] = _shapes(
        walls=(WALL,),
        doors=(Door((200, 100), (260, 100), hinge_at_a=True, toward=(230, 150)),),
    )["door"]
    # Hinge (200, 100), width 60; it opens downwards (toward y 150): leaf to (200, 160).
    assert door["opening_px"] == [[200, 100], [260, 100]]
    assert door["hinge_px"] == [200, 100]
    assert door["leaf_px"] == [[200, 100], [200, 160]]
    arc = door["arc_px"]
    assert isinstance(arc, list) and len(arc) == 13  # 12 steps of 7.5 degrees
    assert arc[0] == [200, 160] and arc[-1] == [260, 100]
    # Halfway, 45 degrees: 200 + 60 cos 45 = 242.4, 100 + 60 sin 45 = 142.4.
    assert arc[6] == [242.4, 142.4]
    assert door["bbox"] == (200, 100, 260, 160)


def test_a_door_hinged_at_its_far_end_opening_the_other_way() -> None:
    [door] = _shapes(doors=(Door((200, 100), (260, 100), hinge_at_a=False, toward=(230, 40)),))[
        "door"
    ]
    # Hinge (260, 100); opens upwards: leaf to (260, 40); the arc ends at (200, 100).
    assert door["leaf_px"] == [[260, 100], [260, 40]]
    assert door["arc_px"][-1] == [200, 100]  # type: ignore[index]
    assert door["bbox"] == (200, 40, 260, 100)


def test_a_window_is_a_thin_double_line_across_its_wall() -> None:
    [window] = _shapes(walls=(WALL,), windows=(Window((300, 100), (380, 100)),))["window"]
    # Lines a quarter of the wall (12 / 4 = 3) either side; end ticks the full 12.
    assert window["lines_px"] == [
        [[300, 103], [380, 103]],
        [[300, 97], [380, 97]],
        [[300, 106], [300, 94]],
        [[380, 106], [380, 94]],
    ]
    assert window["opening_px"] == [[300, 100], [380, 100]]
    assert window["bbox"] == (300, 94, 380, 106)


def test_a_window_off_any_wall_uses_the_inner_thickness() -> None:
    [window] = _shapes(windows=(Window((300, 500), (380, 500)),))["window"]
    # 7 / 4 = 1.75 px off the line, stored to 0.1 px: 501.75 -> 501.8.
    assert window["lines_px"][0] == [[300, 501.8], [380, 501.8]]  # type: ignore[index]


def test_room_names_are_one_size_centred_on_their_point_and_have_no_area() -> None:
    shapes = _shapes(
        rooms=(
            Room("bath", (300, 300), None),
            Room("living room", (500, 500), ((400, 400), (600, 400), (600, 600))),
        )
    )
    bath, living = shapes["room"]
    # "bath": 4 letters x 0.6 x 24 = 57.6 wide, 24 high, centred on (300, 300).
    assert bath["bbox"] == (271.2, 288, 328.8, 312)
    assert bath["text"] == "bath"
    assert bath == {**bath, "label_px": [300, 300], "font_px": 24}
    assert "polygon_px" not in bath
    # With an outline, the room is where its outline is.
    assert living["bbox"] == (400, 400, 600, 600)
    assert living["polygon_px"] == [[400, 400], [600, 400], [600, 600]]
    assert living["outline"] == "approximate"
    for room in (bath, living):
        assert "area_m2" not in room and "value_mm" not in room


def test_written_text_is_kept_as_text() -> None:
    [note] = _shapes(notes=(Note("N", (900, 50)),))["text"]
    # One letter: 0.6 x 16 = 9.6 wide, 16 high.
    assert note["bbox"] == pytest.approx((895.2, 42, 904.8, 58))
    assert note["text"] == "N" and note["written"] is True and note["font_px"] == 16
