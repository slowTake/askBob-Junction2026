from typing import Any

from app.ingest.types import ExtractedElement
from eval.redraw_elements import sheet_from_elements
from eval.redraw_sheet import Opening, Room, Text, Wall

WIDTH = 500  # page width: text size 5 px, room names 7.5 px (1/100 of the width, x1.5)


def el(kind: str, bbox: Any, **kw: Any) -> ExtractedElement:
    return ExtractedElement(kind=kind, source="ocr", bbox=bbox, **kw)


def test_a_wall_keeps_its_outline() -> None:
    outline = [[0, 0], [10, 0], [10, 2], [0, 2]]
    sheet = sheet_from_elements(
        [el("wall", (0, 0, 10, 2), properties={"polygon_px": outline})], WIDTH
    )
    assert sheet.walls == (Wall(((0, 0), (10, 0), (10, 2), (0, 2))),)


def test_a_wall_without_an_outline_is_its_box() -> None:
    sheet = sheet_from_elements([el("wall", (1, 2, 11, 4))], WIDTH)
    # x0,y0 x1,y0 x1,y1 x0,y1, as redraw.ts writes the points
    assert sheet.walls == (Wall(((1, 2), (11, 2), (11, 4), (1, 4))),)


def test_a_malformed_outline_falls_back_to_the_box() -> None:
    two_points = {"polygon_px": [[0, 0], [5, 5]]}  # not a triangle: polygonPoints gives null
    flagged = {"polygon_px": [[0, 0], [5, True], [5, 5]]}  # a boolean is not a finite number
    sheet = sheet_from_elements(
        [
            el("wall", (1, 2, 11, 4), properties=two_points),
            el("wall", (0, 0, 2, 2), properties=flagged),
        ],
        WIDTH,
    )
    assert sheet.walls == (
        Wall(((1, 2), (11, 2), (11, 4), (1, 4))),
        Wall(((0, 0), (2, 0), (2, 2), (0, 2))),
    )


def test_elements_without_an_area_are_not_drawn() -> None:
    sheet = sheet_from_elements(
        [
            el("wall", None),
            el("wall", (5, 0, 5, 10)),  # zero width
            el("door", (0, 3, 4, 3)),  # zero height
            el("room", (0, 0, 0, 0), label="mh"),
        ],
        WIDTH,
    )
    assert sheet == sheet_from_elements([], WIDTH)


def test_an_opening_is_the_centre_line_of_its_box_along_the_long_side() -> None:
    sheet = sheet_from_elements([el("door", (10, 20, 30, 24)), el("window", (5, 10, 7, 40))], WIDTH)
    assert sheet.openings == (
        Opening("door", (10, 22), (30, 22)),  # 20 wide, 4 high: horizontal, y = (20+24)/2
        Opening("window", (6, 10), (6, 40)),  # 2 wide, 30 high: vertical, x = (5+7)/2
    )
    assert sheet.openings[0].hinge is None and sheet.openings[0].toward is None


def test_a_square_opening_is_read_as_horizontal() -> None:
    sheet = sheet_from_elements([el("door", (0, 0, 4, 4))], WIDTH)
    assert sheet.openings == (Opening("door", (0, 2), (4, 2)),)


def test_unclassified_text_needs_confidence_and_a_letter_or_digit() -> None:
    sheet = sheet_from_elements(
        [
            el("text", (0, 0, 10, 4), text="AB", confidence=0.6),  # at the cut: kept
            el("text", (0, 10, 10, 14), text="CD", confidence=0.59),  # below it: dropped
            el("text", (0, 20, 10, 24), text="--", confidence=0.9),  # punctuation only
            el("text", (0, 30, 10, 34), text="ö", confidence=0.9),  # a letter is enough
        ],
        WIDTH,
    )
    assert sheet.texts == (Text("AB", "other", (5, 2)), Text("ö", "other", (5, 32)))


def test_classified_text_is_kept_whatever_its_confidence() -> None:
    sheet = sheet_from_elements(
        [
            el("dimension", (0, 0, 20, 6), text="5,341", label="5,341", confidence=0.1),
            el("room_number", (40, 0, 50, 6), text=" 12 ", label=None, confidence=0.1),
        ],
        WIDTH,
    )
    assert sheet.texts == (
        Text("5,341", "dimension", (10, 3)),
        Text("12", "other", (45, 3)),  # no label: the text, trimmed
    )


def test_blank_labels_are_skipped_and_an_empty_label_hides_the_text() -> None:
    sheet = sheet_from_elements(
        [
            el("dimension", (0, 0, 20, 6), label="   "),
            el("room", (0, 0, 10, 4), label="", text="mh"),  # `??` keeps "": nothing drawn
        ],
        WIDTH,
    )
    assert sheet.texts == () and sheet.rooms == ()


def test_a_room_is_its_name_at_the_box_centre_with_its_outline() -> None:
    outline = [[0, 0], [40, 0], [40, 30], [0, 30]]
    sheet = sheet_from_elements(
        [
            el("room", (10, 10, 20, 14), label="mh", properties={"polygon_px": outline}),
            el("room", (50, 50, 60, 54), label=None, text="KH"),
        ],
        WIDTH,
    )
    assert sheet.rooms == (
        Room("mh", (15, 12), ((0, 0), (40, 0), (40, 30), (0, 30))),
        Room("KH", (55, 52), None),
    )
    assert sheet.texts == ()  # no area_m2: no area line


def test_a_computed_area_is_drawn_under_the_room_name() -> None:
    outline = [[0, 0], [40, 0], [40, 30], [0, 30]]
    room = el(
        "room", (10, 10, 20, 14), label="mh", properties={"polygon_px": outline, "area_m2": 12.25}
    )
    sheet = sheet_from_elements([room], WIDTH)
    # toFixed(1) rounds the tie 12.25 up (Python's format would give 12.2).
    # Room names are 1.5 * 500/100 = 7.5 px; the area sits one name-height lower: 12 + 7.5.
    assert sheet.texts == (Text("12.3 m²", "other", (15, 19.5)),)


def test_no_computed_area_when_the_drawing_prints_one_inside_the_room() -> None:
    outline = [[0, 0], [40, 0], [40, 30], [0, 30]]
    room = el(
        "room", (10, 10, 20, 14), label="mh", properties={"polygon_px": outline, "area_m2": 9.0}
    )
    printed = el("area", (10, 20, 20, 24), label="9,0 m2")  # centre (15, 22) is inside
    sheet = sheet_from_elements([room, printed], WIDTH)
    assert sheet.texts == (Text("9,0 m2", "other", (15, 22)),)


def test_a_printed_area_outside_the_room_does_not_hide_its_area() -> None:
    outline = [[0, 0], [40, 0], [40, 30], [0, 30]]
    room = el(
        "room", (10, 10, 20, 14), label="mh", properties={"polygon_px": outline, "area_m2": 9.0}
    )
    printed = el("area", (100, 100, 110, 104), label="7 m2")
    sheet = sheet_from_elements([room, printed], WIDTH)
    assert Text("9.0 m²", "other", (15, 19.5)) in sheet.texts


def test_a_room_without_an_outline_still_gets_its_area() -> None:
    room = el("room", (10, 10, 20, 14), label="mh", properties={"area_m2": 9.04})
    sheet = sheet_from_elements([room], WIDTH)
    assert sheet.texts == (Text("9.0 m²", "other", (15, 19.5)),)
