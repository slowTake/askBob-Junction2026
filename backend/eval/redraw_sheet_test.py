import pytest

from eval.redraw_sheet import Opening, Room, Text, load_sheet

# A 100 x 200 px page: x is a share of 100, y a share of 200.
W, H = 100, 200


def test_a_wall_run_becomes_a_band_with_square_ends() -> None:
    # (0.1, 0.5)-(0.5, 0.5) is (10, 100)-(50, 100); thickness 0.02 of the width is 2 px,
    # so the band is 1 px either side and runs 1 px past each end: x 9..51, y 99..101.
    sheet = load_sheet({"walls": [{"a": [0.1, 0.5], "b": [0.5, 0.5], "thickness": 0.02}]}, W, H)
    assert set(sheet.walls[0].polygon) == {(9.0, 101.0), (51.0, 101.0), (51.0, 99.0), (9.0, 99.0)}


def test_a_diagonal_wall_keeps_its_direction() -> None:
    # (0, 0)-(0.3, 0.2) is (0, 0)-(30, 40), length 50, unit (0.6, 0.8), normal (-0.8, 0.6).
    # Thickness 0.1 of 100 is 10 px, so half is 5: ends move 5 px along the run (3, 4)
    # and the sides 5 px along the normal (-4, 3): ends (-3, -4) and (33, 44), corners
    # (-3-4, -4+3), (33-4, 44+3), (33+4, 44-3), (-3+4, -4-3).
    sheet = load_sheet({"walls": [{"a": [0, 0], "b": [0.3, 0.2], "thickness": 0.1}]}, W, H)
    corners = {(round(x, 6), round(y, 6)) for x, y in sheet.walls[0].polygon}
    assert corners == {(-7.0, -1.0), (29.0, 47.0), (37.0, 41.0), (1.0, -7.0)}


def test_a_wall_can_be_given_as_its_outline() -> None:
    raw = {"walls": [{"polygon": [[0, 0], [0.5, 0], [0.5, 0.5]]}]}
    assert load_sheet(raw, W, H).walls[0].polygon == ((0.0, 0.0), (50.0, 0.0), (50.0, 100.0))


def test_openings_rooms_and_texts_are_scaled_to_page_pixels() -> None:
    raw = {
        "openings": [
            {"kind": "door", "a": [0.1, 0.1], "b": [0.2, 0.1], "hinge": "b", "toward": [0.15, 0.2]},
            {"kind": "window", "a": [0.5, 0.0], "b": [0.6, 0.0]},
        ],
        "rooms": [{"name": "keittiö", "label": [0.5, 0.5], "polygon": [[0, 0], [1, 0], [1, 1]]}],
        "texts": [{"text": "5,341", "kind": "dimension", "at": [0.25, 0.75], "rotation": 90}],
        "notes": "free text for the author, ignored",
    }
    sheet = load_sheet(raw, W, H)
    assert sheet.openings == (
        Opening("door", (10.0, 20.0), (20.0, 20.0), hinge=(20.0, 20.0), toward=(15.0, 40.0)),
        Opening("window", (50.0, 0.0), (60.0, 0.0)),
    )
    assert sheet.rooms == (
        Room("keittiö", (50.0, 100.0), ((0.0, 0.0), (100.0, 0.0), (100.0, 200.0))),
    )
    assert sheet.texts == (Text("5,341", "dimension", (25.0, 150.0), 90),)


def test_an_empty_truth_is_an_empty_sheet() -> None:
    sheet = load_sheet({}, W, H)
    assert (sheet.walls, sheet.openings, sheet.rooms, sheet.texts) == ((), (), (), ())


@pytest.mark.parametrize(
    "raw",
    [
        {"walls": [{"a": [0.1, 0.1], "b": [0.1, 0.1], "thickness": 0.01}]},  # no length
        {"walls": [{"a": [0.1, 0.1], "b": [0.2, 0.1], "thickness": 0}]},  # no thickness
        {"walls": [{"polygon": [[0, 0], [1, 1]]}]},  # not a polygon
        {"openings": [{"kind": "stair", "a": [0, 0], "b": [0.1, 0]}]},
        {"openings": [{"kind": "door", "a": [0, 0], "b": [0.1, 0], "hinge": "c"}]},
        {"openings": [{"kind": "door", "a": [0, 0], "b": [0.1, 0], "hinge": [0, 0]}]},
        {"rooms": [{"name": " ", "label": [0.5, 0.5]}]},
        {"texts": [{"text": "x", "kind": "dimension", "at": [0.5, 0.5], "rotation": 45}]},
        {"texts": [{"text": "x", "kind": "graffiti", "at": [0.5, 0.5]}]},
        {"texts": [{"text": "x", "kind": "other", "at": [1.5, 0.5]}]},  # off the page
        {"texts": [{"text": "x", "kind": "other", "at": [True, 0.5]}]},
        {"walls": "not a list"},
    ],
)
def test_a_malformed_truth_is_refused_not_repaired(raw: object) -> None:
    with pytest.raises(ValueError):
        load_sheet(raw, W, H)
