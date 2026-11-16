import pytest

from app.domain.redraw_confidence import (
    CONFIDENCE_FORMAT,
    Mark,
    PartScore,
    RedrawConfidence,
    Shape,
    confidence_from_meta,
    confidence_meta,
    drawn_shape,
    score,
)

W = 482  # the benchmark page: text is 4.82 px, room names 7.23 px


def shape(
    kind: str, bbox: tuple[float, float, float, float] | None, **over: object
) -> Shape | None:
    fields: dict[str, object] = {
        "label": None, "text": None, "confidence": 0.9, "properties": {},
    }  # fmt: skip
    fields.update(over)
    return drawn_shape(kind, bbox, page_width=W, **fields)  # type: ignore[arg-type]


def flat(polygon: tuple[tuple[float, float], ...]) -> list[float]:
    return [v for point in polygon for v in point]


def test_a_wall_is_its_outline_else_its_box() -> None:
    box = shape("wall", (10, 20, 30, 40))
    assert box == Shape("walls", ((10, 20), (30, 20), (30, 40), (10, 40)))
    outline = [[10, 20], [30, 20], [20, 40]]
    assert shape("wall", (10, 20, 30, 40), properties={"polygon_px": outline}) == Shape(
        "walls", ((10, 20), (30, 20), (20, 40))
    )
    # Not an outline (two points, a string): the box is drawn, as redraw.ts does.
    assert shape("wall", (10, 20, 30, 40), properties={"polygon_px": [[1, 2], [3, 4]]}) == box
    assert shape("wall", (10, 20, 30, 40), properties={"polygon_px": "no"}) == box


def test_doors_and_windows_are_their_boxes() -> None:
    assert shape("door", (0, 0, 8, 2)) == Shape("openings", ((0, 0), (8, 0), (8, 2), (0, 2)))
    assert shape("window", (0, 0, 2, 8)) == Shape("openings", ((0, 0), (2, 0), (2, 8), (0, 8)))


def test_a_room_name_is_drawn_at_the_box_centre_in_the_room_size() -> None:
    # Centre (100, 150); room size 1.5 x 4.82 = 7.23 px; "mh" is two glyphs 0.6 em wide:
    # half width 0.6 x 7.23 x 2 / 2 = 4.338, half height 3.615.
    s = shape("room", (90, 140, 110, 160), label="mh", text="MH ")
    assert s is not None and s.part == "rooms"
    assert flat(s.polygon) == pytest.approx(
        [95.662, 146.385, 104.338, 146.385, 104.338, 153.615, 95.662, 153.615]
    )


def test_dimensions_heights_and_other_labels_are_drawn_in_the_text_size() -> None:
    # Size 4.82 px, "5,341" is 5 glyphs: half width 0.6 x 4.82 x 5 / 2 = 7.23, half height 2.41.
    d = shape("dimension", (0, 0, 20, 10), label="5,341")
    assert d is not None and d.part == "dimensions"
    assert flat(d.polygon) == pytest.approx([2.77, 2.59, 17.23, 2.59, 17.23, 7.41, 2.77, 7.41])
    h = shape("height", (0, 0, 20, 10), label="h1600")
    assert h is not None and h.part == "heights"
    a = shape("area", (0, 0, 20, 10), label="12,5 m2")
    assert a is not None and a.part == "text"


def test_what_the_view_leaves_out_is_not_drawn() -> None:
    assert shape("wall", None) is None
    assert shape("wall", (10, 10, 10, 20)) is None  # no area
    assert shape("room", (0, 0, 20, 10), label=" ", text="mh") is None  # an empty label wins
    assert shape("text", (0, 0, 20, 10), text="...") is None  # no letter or digit
    assert shape("text", (0, 0, 20, 10), text="mh", confidence=0.59) is None  # too unsure
    assert shape("text", (0, 0, 20, 10), text="mh", confidence=0.6) is not None
    assert shape("dimension", (0, 0, 20, 10), text="5,341", confidence=0.2) is not None


def test_the_score_is_the_harmonic_mean_of_covered_and_on_ink() -> None:
    assert score(1.0, 1.0) == 1.0
    assert score(0.8, 1.0) == pytest.approx(2 * 0.8 / 1.8)  # 0.889
    assert score(0.0, 1.0) == 0.0
    assert score(0.0, 0.0) == 0.0


CONFIDENCE = RedrawConfidence(
    score=0.88888,
    covered=0.8,
    on_ink=1.0,
    ink_px=3481,
    parts={
        "walls": PartScore(count=2, drawn_px=3381, on_ink=1.0, ink_covered=0.97127),
        "openings": PartScore(count=0, drawn_px=0, on_ink=1.0, ink_covered=0.0),
    },
    missed=(
        Mark(polygon=((298.0, 298.0), (311.0, 298.0), (311.0, 311.0), (298.0, 311.0)), px=100),
    ),
    added=(),
)


def test_the_stored_entry_rounds_and_the_api_reads_it_back() -> None:
    meta = confidence_meta(CONFIDENCE)
    assert meta["format"] == CONFIDENCE_FORMAT
    assert (meta["score"], meta["covered"], meta["on_ink"], meta["ink_px"]) == (
        0.889,
        0.8,
        1.0,
        3481,
    )
    assert meta["parts"]["walls"] == {
        "count": 2, "drawn_px": 3381, "on_ink": 1.0, "ink_covered": 0.971,
    }  # fmt: skip
    assert meta["missed"] == [
        {"polygon": [[298, 298], [311, 298], [311, 311], [298, 311]], "px": 100}
    ]
    assert meta["added"] == []
    out = confidence_from_meta(meta)
    assert out is not None and "format" not in out
    assert out["score"] == 0.889 and out["parts"]["walls"]["count"] == 2


def test_a_missing_old_or_malformed_entry_is_not_served() -> None:
    assert confidence_from_meta(None) is None
    assert confidence_from_meta({**confidence_meta(CONFIDENCE), "format": 0}) is None
    broken = confidence_meta(CONFIDENCE)
    del broken["parts"]
    assert confidence_from_meta(broken) is None
    assert confidence_from_meta({**confidence_meta(CONFIDENCE), "score": "high"}) is None
