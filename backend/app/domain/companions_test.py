from app.domain.companions import Candidate, companion_matches, drawing_stem, matching_id


def test_matching_floor_names_ignore_extension_and_case() -> None:
    assert companion_matches("Floor-1.PNG", "floor-1.dxf")
    assert not companion_matches("floor-1.png", "floor-2.dxf")


def test_paths_and_multiple_dots() -> None:
    assert drawing_stem("C:\\plans\\floor.1.PNG") == "floor.1"
    assert companion_matches("/plans/floor.1.png", "floor.1.dxf")
    assert not companion_matches("", "")


def test_repeated_identical_files_are_safe_but_different_revisions_are_ambiguous() -> None:
    a = Candidate("a", "floor.dxf", "same", "ready")
    b = Candidate("b", "floor.DXF", "same", "queued")
    assert matching_id("floor.png", [b, a]) == "a"
    assert matching_id("floor.png", [a, Candidate("c", "floor.dxf", "other", "ready")]) is None
    assert matching_id("other.png", [a]) is None
    assert matching_id("floor.png", [Candidate("c", "floor.dxf", "same", "failed")]) is None
