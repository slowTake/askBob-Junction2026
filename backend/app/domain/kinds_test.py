from app.domain.kinds import DRAWING_KINDS


def test_drawing_kinds_include_the_vocabulary_kinds() -> None:
    # Issue #43: classify() in tokens.py (room, fixture from vocab codes, door, dimension,
    # scale, area, text; room_number and unit from Swiss labels such as "2.01" and
    # "Whg. A") plus the wall candidates from annotate.py.
    expected = {"room", "room_number", "unit", "fixture", "door", "dimension", "scale",
                "area", "text", "wall"}  # fmt: skip
    assert expected == DRAWING_KINDS
