import math

import cv2
import numpy as np
import pytest

from app.domain.geometry import polygon_area
from app.domain.polygons import point_in_polygon, polygon_bbox
from app.ingest.wall_trace import TracedWall, model_walls_beyond, trace_walls

RUN = 20  # the shortest wall run in these tests, px


def _page(h: int = 120, w: int = 160) -> np.ndarray:
    return np.zeros((h, w), dtype=bool)


def _walls(ink: np.ndarray, **kw: object) -> list[TracedWall]:
    return trace_walls(ink, min_run_px=RUN, **kw)  # type: ignore[arg-type]


def _covers(wall: TracedWall, x: float, y: float) -> bool:
    return point_in_polygon((x, y), wall.polygon)


def test_an_l_shaped_band_is_one_polygon() -> None:
    ink = _page()
    ink[10:16, 10:70] = True  # arm along x: 60 x 6 px
    ink[10:70, 10:16] = True  # arm along y: 6 x 60 px, sharing the corner
    (wall,) = _walls(ink)
    assert wall.drawn == "band"
    # 6 px thick: the skeleton runs on row 12 or 13, 3 px from the paper either side.
    assert wall.thickness_px == pytest.approx(6, abs=0.5)
    assert _covers(wall, 40, 12.5) and _covers(wall, 12.5, 40)  # both arms
    assert not _covers(wall, 40, 40)  # not the box around the L


def test_a_band_at_30_degrees_is_one_polygon_not_a_box() -> None:
    ink = _page()
    end = (20 + round(80 * math.cos(math.radians(30))), 20 + round(80 * math.sin(math.radians(30))))
    canvas = np.zeros(ink.shape, np.uint8)
    cv2.line(canvas, (20, 20), end, 1, thickness=6)  # to (89, 60)
    (wall,) = _walls(canvas > 0)
    assert wall.drawn == "band"
    # About 80 x 6 = 480 px of band; its box is about 75 x 46 = 3450 px.
    x0, y0, x1, y1 = polygon_bbox(wall.polygon)
    assert polygon_area(wall.polygon) < 0.3 * (x1 - x0) * (y1 - y0)
    assert polygon_area(wall.polygon) == pytest.approx(480, rel=0.25)
    assert _covers(wall, 55, 40)  # the middle of the line: (20 + 89) / 2, (20 + 60) / 2


def test_a_hatched_band_is_one_solid_polygon() -> None:
    ink = _page()
    ink[30, 10:110] = True  # 100 px band, rows 30..39: two edges
    ink[39, 10:110] = True
    for x in range(10, 110, 4):  # a diagonal hatch line every 4 px, 10 px long
        for d in range(10):
            if x + d < 110:
                ink[30 + d, x + d] = True
    (wall,) = _walls(ink)
    assert wall.drawn == "band"
    assert wall.thickness_px == pytest.approx(10, abs=1)  # rows 30..39
    assert _covers(wall, 60, 34.5)  # inside the band, between hatch lines


def test_handwriting_inside_a_word_box_is_not_a_wall() -> None:
    canvas = np.zeros((120, 160), np.uint8)
    cv2.putText(canvas, "aula", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 1, thickness=4)
    assert _walls(canvas > 0, text_boxes=[(15.0, 30.0, 110.0, 70.0)]) == []


def test_handwriting_the_ocr_missed_is_not_a_wall() -> None:
    canvas = np.zeros((120, 200), np.uint8)
    for i in range(12):  # small cursive loops drawn with a 1 px pen: "eeee..."
        cv2.circle(canvas, (20 + 7 * i, 60), 3, 1, thickness=1)
    # Closed over, the loops are a solid band 7 px thick and 84 long (x 17..100), but
    # no stroke of theirs runs straight for 9 px.
    assert _walls(canvas > 0) == []


def test_a_blob_shorter_than_a_run_is_not_a_wall() -> None:
    ink = _page()
    ink[50:62, 50:62] = True  # a 12 px square: a fixture symbol, not a wall run of 20
    assert _walls(ink) == []


def test_a_dashed_line_is_not_a_wall() -> None:
    ink = _page()
    for x in range(10, 150, 14):
        ink[60, x : x + 8] = True  # 8 px dashes, 6 px gaps: no run of 20
    assert _walls(ink) == []


def test_a_thin_wall_line_is_kept_with_its_thickness() -> None:
    ink = _page()
    ink[40, 10:90] = True  # 1 px, 80 long
    ink[20:100, 120:122] = True  # 2 px, 80 long
    walls = sorted(_walls(ink), key=lambda w: polygon_bbox(w.polygon)[0])
    assert [w.drawn for w in walls] == ["line", "line"]
    assert [w.thickness_px for w in walls] == [1.0, 2.0]  # 80 px / 80 and 160 px / 80
    # Each polygon is the run's pixels to their edges: columns 10..89 are x 9.5..89.5.
    assert polygon_bbox(walls[0].polygon) == (9.5, 39.5, 89.5, 40.5)
    assert polygon_bbox(walls[1].polygon) == (119.5, 19.5, 121.5, 99.5)


def test_a_slightly_tilted_thin_line_is_one_run() -> None:
    ink = _page()
    ink[40, 10:50] = True  # a scanned line that steps down one row half way
    ink[41, 50:90] = True
    (wall,) = _walls(ink)
    assert wall.thickness_px == 1.0  # 80 px over 80 columns
    # Drawn along the fitted line, 1 px thick: 80 x 1 = 80 px, not its 80 x 2 box.
    assert polygon_area(wall.polygon) == pytest.approx(80, abs=1)
    assert _covers(wall, 30, 40) and _covers(wall, 70, 41)


def test_a_dimension_line_is_not_a_wall() -> None:
    ink = _page()
    ink[50, 10:70] = True  # the dimension line, broken by a tick at x 70..71
    ink[46:55, 70] = True
    ink[50, 72:150] = True  # its continuation past the tick
    ink[90, 10:150] = True  # a wall line farther away
    label = (30.0, 40.0, 50.0, 48.0)  # "5,341" above the first part, 8 px tall
    (wall,) = _walls(ink, dimension_boxes=[label])
    assert polygon_bbox(wall.polygon)[1] == 89.5  # only the wall line on row 90


def test_a_dimension_line_cut_by_its_own_label_is_not_a_wall() -> None:
    ink = _page()
    ink[50, 10:150] = True  # the dimension line, running under its label
    label = (60.0, 44.0, 90.0, 54.0)  # erased as text: the line is left as 10..59 and 91..149
    assert _walls(ink, text_boxes=[label], dimension_boxes=[label]) == []


def test_a_wall_network_never_covers_its_rooms() -> None:
    ink = _page()
    ink[10:16, 10:150] = True  # two rooms side by side, walls 6 px thick
    ink[100:106, 10:150] = True
    ink[10:106, 10:16] = True
    ink[10:106, 77:83] = True
    ink[10:106, 144:150] = True
    walls = _walls(ink)
    assert {w.drawn for w in walls} == {"band"}
    assert len(walls) >= 2
    for room in ((45, 58), (113, 58)):
        assert not any(_covers(w, *room) for w in walls)
    for wall_point in ((45, 12.5), (80, 58), (12.5, 58), (113, 102.5)):
        assert any(_covers(w, *wall_point) for w in walls)


def test_a_ring_with_no_junction_never_covers_its_room() -> None:
    ink = _page()
    ink[20:26, 20:100] = True  # a closed square ring of 6 px walls
    ink[80:86, 20:100] = True
    ink[20:86, 20:26] = True
    ink[20:86, 94:100] = True
    walls = _walls(ink)
    assert walls
    assert not any(_covers(w, 60, 53) for w in walls)
    assert any(_covers(w, 60, 22.5) for w in walls) and any(_covers(w, 60, 82.5) for w in walls)


def test_a_thin_line_meeting_a_band_is_traced_once_each() -> None:
    ink = _page()
    ink[10:16, 10:110] = True  # a band
    ink[16:100, 60] = True  # a 1 px partition hanging from it, 84 long
    walls = _walls(ink)
    assert sorted(w.drawn for w in walls) == ["band", "line"]
    line = next(w for w in walls if w.drawn == "line")
    x0, y0, x1, _ = polygon_bbox(line.polygon)
    assert (x0, x1) == (59.5, 60.5)
    assert y0 >= 15.5  # starts at the band, not inside it


def test_blank_paper_has_no_walls() -> None:
    assert _walls(_page()) == []


def test_a_carved_symbol_is_not_traced_into_the_wall_beside_it() -> None:
    ink = _page()
    ink[50:56, 10:150] = True  # a band 6 px thick, rows 50..55
    ink[44, 40:70] = ink[47, 40:70] = True  # a window frame 2 px above it, rows 44..47
    ink[44:48, 40] = ink[44:48, 69] = True
    merged = _walls(ink)  # closing joins the frame into the band (gap of 2 rows)
    assert any(_covers(w, 55, 45.5) for w in merged)
    carve = _page()
    carve[44:48, 40:70] = True  # the frame's box
    (wall,) = _walls(ink, carve=carve)
    assert not _covers(wall, 55, 45.5)  # the frame is gone
    assert wall.thickness_px == pytest.approx(6, abs=0.5)  # and the band is as it was
    assert _covers(wall, 55, 52.5)  # it runs on past the window: no gap is cut


# --- the floor-plan model's walls join the traced ones -----------------------------


def test_a_model_wall_over_a_traced_wall_gives_way_to_the_ink() -> None:
    ink = _page()
    ink[10:16, 10:110] = True  # a band the trace finds
    traced = _walls(ink)
    over = [(10.0, 9.0), (110.0, 9.0), (110.0, 17.0), (10.0, 17.0)]  # the model's copy of it
    beside = [(10.0, 80.0), (110.0, 80.0), (110.0, 86.0), (10.0, 86.0)]  # one the trace missed
    assert model_walls_beyond(traced, [over, beside], ink.shape) == [beside]


def test_model_walls_are_all_kept_when_nothing_was_traced() -> None:
    wall = [(10.0, 80.0), (110.0, 80.0), (110.0, 86.0), (10.0, 86.0)]
    assert model_walls_beyond([], [wall], (120, 160)) == [wall]
