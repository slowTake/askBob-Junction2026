"""Write a model with our IFC writer, read it back with our reader and mesher."""

from pathlib import Path

import pytest

from app.bim.ifc_mesh import ifc_to_mesh
from app.bim.ifc_writer import BimItem, write_ifc
from app.config import Settings
from app.ingest.ifc_reader import read_ifc

ROOM = [(0.0, 0.0), (3030.0, 0.0), (3030.0, 3415.0), (0.0, 3415.0)]
WALL = [(0.0, -200.0), (3030.0, -200.0), (3030.0, 0.0), (0.0, 0.0)]


@pytest.fixture
def model_path(tmp_path: Path) -> Path:
    items = [
        BimItem("r1", "room", "MH", "bedroom (MH)", ROOM, None, {"Page": 0, "Confidence": 0.5}),
        BimItem("w1", "wall", None, None, WALL, None, {"Page": 0}),
        BimItem("d1", "door", "09", "door 900 mm", None, 900, {"Page": 0}),
        BimItem("x1", "room", "OH", None, None, None),  # no footprint: skipped
    ]
    path = tmp_path / "model.ifc"
    guids = write_ifc(items, path, project_name="test")
    assert set(guids) == {"r1", "w1", "d1"}
    return path


def test_reader_sees_written_elements(model_path: Path) -> None:
    settings = Settings(database_url="x", valkey_url="x")
    doc = read_ifc(model_path, settings, lambda stage, fraction: None)
    by_kind = {e.kind: e for e in doc.elements}
    assert by_kind["room"].name == "bedroom (MH)"
    assert by_kind["room"].properties["Bob_Provenance.Confidence"] == 0.5
    assert by_kind["room"].properties["storey"] == "Floor 1"
    assert by_kind["door"].value_mm == 900.0  # file is in mm, so 900 stays 900
    assert doc.meta["length_unit_mm"] == pytest.approx(1.0)


def test_mesh_has_room_extent_in_metres(model_path: Path) -> None:
    meshes = ifc_to_mesh(model_path)["meshes"]
    room = next(m for m in meshes if m["ifc_class"] == "IfcSpace")
    xs = room["positions"][0::3]
    heights = room["positions"][1::3]
    # 3030 mm wide room -> 3.03 m; extruded 2600 mm -> 2.6 m high (Y-up after conversion).
    assert (min(xs), max(xs)) == (0.0, 3.03)
    assert (min(heights), max(heights)) == (0.0, 2.6)
    assert len(room["indices"]) % 3 == 0
