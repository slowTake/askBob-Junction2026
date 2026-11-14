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


def test_model_room_gives_a_printed_label_its_outline() -> None:
    elements, _, _ = annotate_page(_blank(), [KITCHEN_LABEL], "ocr", None, vision=VISION)
    kitchen = next(e for e in elements if e.text == "Küche")
    assert kitchen.properties["polygon_px"] == [[10, 10], [110, 10], [110, 110], [10, 110]]
    assert "region" not in kitchen.properties


def test_unlabelled_model_rooms_and_objects_become_elements() -> None:
    elements, _, _ = annotate_page(_blank(), [KITCHEN_LABEL], "ocr", None, vision=VISION)
    from_model = [(e.kind, e.properties.get("category") or e.properties.get("subtype"))
                  for e in elements if e.source == "vision"]  # fmt: skip
    assert ("room", "bathroom") in from_model
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
