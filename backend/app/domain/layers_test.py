from app.domain.layers import layer_role, units_to_mm


def test_swiss_dataset_layers() -> None:
    # Layer names from data/swiss_dwellings/*.dxf in the Junction dataset.
    assert layer_role("WALL") == "wall"
    assert layer_role("DOOR") == "door"
    assert layer_role("WINDOW") == "window"
    assert layer_role("ROOM_OUTLINE") == "room"
    assert layer_role("ROOM_TEXT") == "text"
    assert layer_role("UNIT_OUTLINE") == "unit"
    assert layer_role("FIXTURE") == "fixture"
    assert layer_role("ANNOTATION") == "text"


def test_other_languages_and_unknown() -> None:
    assert layer_role("A-Wand-tragend") == "wall"
    assert layer_role("Fenêtres") == "window"
    assert layer_role("0") is None


def test_units() -> None:
    assert units_to_mm(6) == 1000.0  # metres
    assert units_to_mm(4) == 1.0  # millimetres
    assert units_to_mm(1) == 25.4  # inches
    assert units_to_mm(0) is None
    assert units_to_mm(None) is None
