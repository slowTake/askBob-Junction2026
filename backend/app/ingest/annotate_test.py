import numpy as np
import pytest

from app.domain.tokens import Word
from app.domain.vision import parse
from app.ingest.annotate import annotate_page


def _sheet() -> np.ndarray:
    """200x400 white page: dimension line on row 100 from x = 40 to 360, extension
    lines at x = 50, 150 and 350 (rows 88..112). Segments: 100 px and 200 px."""
    page = np.full((200, 400), 255, np.uint8)
    page[100, 40:361] = 0
    for x in (50, 150, 350):
        page[88:113, x] = 0
    return page


WORDS = [
    Word((85.0, 84.0, 115.0, 96.0), "1000"),  # over 50..150
    Word((235.0, 84.0, 265.0, 96.0), "2000"),  # over 150..350
]


def test_scale_from_dpi_and_scale_note() -> None:
    words = [*WORDS, Word((300.0, 150.0, 340.0, 162.0), "1:50")]
    _, scale, meta = annotate_page(_sheet(), words, "ocr", dpi=150.0)
    # 25.4 / 150 * 50 = 8.4667 mm per pixel; the note wins over the dimensions.
    assert scale == pytest.approx(8.46667, rel=1e-4)
    assert meta["scale_method"] == "dpi"


def test_scale_fitted_from_dimensions_without_dpi() -> None:
    _, scale, meta = annotate_page(_sheet(), WORDS, "ocr", dpi=None)
    # 1000 mm / 100 px and 2000 mm / 200 px: 10 mm per pixel, two labels agree.
    assert scale == pytest.approx(10.0)
    assert meta["scale_method"] == "dimension_fit"
    assert meta["scale_support"] == 2
    assert meta["scale_known"] is True


def test_no_scale_when_nothing_to_fit() -> None:
    _, scale, meta = annotate_page(_sheet(), WORDS[:1], "ocr", dpi=None)
    assert scale is None  # one label alone is not trusted
    assert meta["scale_method"] is None
    assert meta["scale_known"] is False


# --- the floor-plan model's output (D-022) --------------------------------------


def _square(x: float, y: float, side: float) -> list[list[float]]:
    return [[x, y], [x + side, y], [x + side, y + side], [x, y + side]]


VISION = parse(
    {
        "rooms": [
            {"class": "Kitchen", "polygon": _square(10, 10, 100)},
            {"class": "Bath", "polygon": _square(200, 10, 60)},
        ],
        "walls": [_square(0, 150, 10)],
        "objects": [
            {"class": "Door", "polygon": [[20, 110], [60, 110], [60, 116], [20, 116]]},
            {"class": "Toilet", "polygon": _square(210, 20, 10)},
        ],
    }
)
KITCHEN_LABEL = Word((40.0, 45.0, 80.0, 55.0), "Küche")  # centre (60, 50): in the kitchen


def _blank() -> np.ndarray:
    return np.full((300, 300), 255, np.uint8)


def test_model_mask_does_not_claim_to_be_a_room_boundary() -> None:
    elements, _, _ = annotate_page(_blank(), [KITCHEN_LABEL], "ocr", None, vision=VISION)
    kitchen = next(e for e in elements if e.text == "Küche")
    assert "polygon_px" not in kitchen.properties
    assert kitchen.properties["region"] == "not_closed"


def test_model_objects_are_kept_without_adding_unlabelled_room_fragments() -> None:
    elements, _, _ = annotate_page(_blank(), [KITCHEN_LABEL], "ocr", None, vision=VISION)
    from_model = [(e.kind, e.properties.get("category") or e.properties.get("subtype"))
                  for e in elements if e.source == "vision"]  # fmt: skip
    assert not [e for e in elements if e.source == "vision" and e.kind == "room"]
    assert ("door", None) in from_model
    assert ("fixture", "wc") in from_model
    assert ("room", "kitchen") not in from_model  # the printed label already names it


def test_model_walls_replace_the_pixel_heuristic() -> None:
    elements, _, _ = annotate_page(_blank(), [], "ocr", None, vision=VISION)
    walls = [e for e in elements if e.kind == "wall"]
    assert [w.source for w in walls] == ["vision"]
    assert walls[0].bbox == (0, 150, 10, 160)


def test_objects_only_keeps_rooms_and_walls_from_the_drawing() -> None:
    elements, _, _ = annotate_page(
        _blank(), [KITCHEN_LABEL], "pdf_text", None, vision=VISION, vision_objects_only=True
    )
    kitchen = next(e for e in elements if e.text == "Küche")
    assert "polygon_px" not in kitchen.properties  # flood fill on a blank page leaks out
    assert not [e for e in elements if e.source == "vision" and e.kind in ("room", "wall")]
    assert [e.kind for e in elements if e.source == "vision"] == ["door", "fixture"]


def test_door_width_in_mm_when_the_scale_is_known() -> None:
    words = [Word((250.0, 250.0, 290.0, 262.0), "1:50")]
    elements, scale, _ = annotate_page(_blank(), words, "ocr", 150.0, vision=VISION)
    door = next(e for e in elements if e.kind == "door")
    # 40 px long side * 25.4 / 150 * 50 mm/px = 338.67 mm (by hand); footprint set too.
    assert scale == pytest.approx(8.46667, rel=1e-4)
    assert door.value_mm == pytest.approx(338.67, abs=0.01)
    assert door.footprint_mm is not None


# --- rooms traced from the drawing's lines (D-024) ------------------------------


def _two_rooms_with_a_door() -> np.ndarray:
    """300 x 200 page: a 3 px wall rectangle (20..280 x 20..180) split at x=150 by a
    wall with a doorway (y 80..120) that a door leaf and swing close."""
    import cv2

    page = np.full((200, 300), 255, np.uint8)
    cv2.rectangle(page, (20, 20), (280, 180), 0, 3)
    cv2.line(page, (150, 20), (150, 80), 0, 3)
    cv2.line(page, (150, 120), (150, 180), 0, 3)
    cv2.line(page, (150, 80), (190, 80), 0, 1)  # leaf
    cv2.ellipse(page, (150, 80), (40, 40), 0, 0, 90, 0, 1)  # swing to the far jamb
    return page


ROOM_WORDS = [Word((60.0, 95.0, 110.0, 110.0), "Küche"), Word((200.0, 140.0, 240.0, 155.0), "Bad")]


def test_printed_rooms_take_outlines_traced_from_the_lines() -> None:
    elements, _, meta = annotate_page(_two_rooms_with_a_door(), ROOM_WORDS, "ocr", None)
    kitchen = next(e for e in elements if e.text == "Küche")
    bath = next(e for e in elements if e.text == "Bad")
    assert kitchen.properties["outline_source"] == "traced"
    assert bath.properties["outline_source"] == "traced"
    xs = [p[0] for p in kitchen.properties["polygon_px"]]
    # Kitchen: from the outer wall (x ~20) to at least the middle wall (x ~150).
    # Known limit (D-024): the doorway itself isn't drawn, so the door's swing area
    # (x 150..190) opens onto the kitchen and is counted in it until doorways are closed.
    assert min(xs) < 30 and 140 < max(xs) < 195
    assert kitchen.properties["polygon_px"] != bath.properties["polygon_px"]
    assert meta["room_outlines"] == {"traced": 2}


def test_without_closed_lines_only_the_printed_room_label_is_available() -> None:
    elements, _, meta = annotate_page(_blank(), [KITCHEN_LABEL], "ocr", None, vision=VISION)
    kitchen = next(e for e in elements if e.text == "Küche")
    assert "polygon_px" not in kitchen.properties
    assert meta["room_outlines"] == {}


def test_another_rooms_number_stops_a_merged_region_being_one_room() -> None:
    # One closed region holds the kitchen's name and another room's number ("1.02",
    # linked to no name): it is two rooms run together, so the kitchen doesn't get it.
    import cv2

    page = np.full((400, 600), 255, np.uint8)  # the region is ~17% of the page: a room size
    cv2.rectangle(page, (20, 20), (280, 180), 0, 3)
    words = [Word((40.0, 90.0, 90.0, 105.0), "Küche"), Word((220.0, 90.0, 250.0, 105.0), "1.02")]
    elements, _, _ = annotate_page(page, words, "ocr", None)
    kitchen = next(e for e in elements if e.text == "Küche")
    assert "polygon_px" not in kitchen.properties
    assert kitchen.properties["region"] == "not_closed"


def test_merged_model_room_is_rejected_without_scale_or_printed_area() -> None:
    vision = parse({"rooms": [{"class": "Bath", "polygon": _square(10, 10, 270)}]})
    words = [KITCHEN_LABEL, Word((210.0, 45.0, 240.0, 55.0), "Bad")]
    elements, _, _ = annotate_page(_blank(), words, "ocr", None, vision=vision)
    rooms = [e for e in elements if e.kind == "room"]
    assert len(rooms) == 2
    assert all("polygon_px" not in e.properties for e in rooms)
    assert all(e.properties["region"] == "not_closed" for e in rooms)


def test_a_smaller_model_fragment_is_not_used_to_replace_a_missing_boundary() -> None:
    vision = parse(
        {
            "rooms": [
                {"class": "Undefined", "polygon": _square(10, 10, 270)},
                {"class": "Kitchen", "polygon": _square(10, 10, 100)},
            ]
        }
    )
    words = [KITCHEN_LABEL, Word((210.0, 45.0, 240.0, 55.0), "Bad")]
    elements, _, meta = annotate_page(_blank(), words, "ocr", None, vision=vision)
    kitchen = next(e for e in elements if e.text == "Küche")
    bath = next(e for e in elements if e.text == "Bad")
    assert "polygon_px" not in kitchen.properties
    assert "polygon_px" not in bath.properties
    assert meta["room_outlines"] == {}


def test_unlinked_room_number_also_rejects_a_merged_model_fallback() -> None:
    vision = parse({"rooms": [{"class": "Bath", "polygon": _square(10, 10, 270)}]})
    words = [KITCHEN_LABEL, Word((220.0, 90.0, 250.0, 105.0), "1.02")]
    elements, _, _ = annotate_page(_blank(), words, "ocr", None, vision=vision)
    kitchen = next(e for e in elements if e.text == "Küche")
    assert "polygon_px" not in kitchen.properties
    assert kitchen.properties["region"] == "not_closed"
    assert not [e for e in elements if e.source == "vision" and e.kind == "room"]
