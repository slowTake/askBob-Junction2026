from app.domain.kinds import DRAWING_KINDS


def test_drawing_kinds_include_the_vocabulary_kinds() -> None:
    # Issue #43: classify() in tokens.py (room, fixture from vocab codes, door, dimension,
    # scale, area, text) plus the wall candidates from annotate.py.
    expected = {"room", "fixture", "door", "dimension", "scale", "area", "text", "wall"}
    assert expected == DRAWING_KINDS
