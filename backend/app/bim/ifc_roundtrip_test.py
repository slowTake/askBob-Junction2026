"""Drawings go through IFC and come back unchanged; uploaded IFC follows the counting rules."""

from pathlib import Path

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.project
import ifcopenshell.api.root
import ifcopenshell.api.unit
import ifcopenshell.guid
import pytest

from app.bim.ifc_index import index_ifc
from app.bim.ifc_mesh import ifc_to_mesh
from app.bim.ifc_writer import write_model
from app.ingest.types import ExtractedElement

ROOM = [(0.0, 0.0), (3030.0, 0.0), (3030.0, 3415.0), (0.0, 3415.0)]
WALL = [(0.0, -200.0), (3030.0, -200.0), (3030.0, 0.0), (0.0, 0.0)]
WINDOW = [(1000.0, -200.0), (2000.0, -200.0), (2000.0, 0.0), (1000.0, 0.0)]


def _drawing() -> list[ExtractedElement]:
    return [
        ExtractedElement("unit", "dxf", label="A", name="apartment A", page_index=0),
        ExtractedElement(
            "room", "dxf", text="Zimmer", label="Zimmer", name="room (Zimmer) 2.01",
            footprint_mm=ROOM, bbox=(10, 20, 30, 40), page_index=0, confidence=1.0,
            properties={"number": "2.01", "unit": "A", "area_m2": 10.35, "outdoor": False},
        ),
        ExtractedElement("wall", "dxf", footprint_mm=WALL, page_index=0, confidence=0.95),
        ExtractedElement("window", "dxf", footprint_mm=WINDOW, value_mm=1000, page_index=0),
        ExtractedElement(
            "door", "pdf_text", label="09", value_mm=900, bbox=(1, 2, 3, 4), page_index=0
        ),
        ExtractedElement("fixture", "dxf", properties={"subtype": "wc"}, page_index=0),
        ExtractedElement("dimension", "pdf_text", text="10 800", label="10 800", value_mm=10800,
                         bbox=(5, 6, 7, 8), page_index=1, confidence=0.7),
    ]  # fmt: skip


@pytest.fixture
def written(tmp_path: Path) -> tuple[list[ExtractedElement], list[ExtractedElement], Path]:
    source = _drawing()
    path = tmp_path / "model.ifc"
    guids = write_model(source, path, project_name="test")
    assert len(guids) == len(source) and len(set(guids)) == len(guids)
    indexed, _ = index_ifc(path)
    return source, indexed, path


def test_every_element_comes_back(written: tuple) -> None:
    source, indexed, _ = written
    # Plus the storey the writer creates, which IFC uploads report too.
    assert sorted(e.kind for e in indexed) == sorted([e.kind for e in source] + ["storey"])


def test_fields_survive_the_round_trip(written: tuple) -> None:
    _, indexed, _ = written
    room = next(e for e in indexed if e.kind == "room")
    assert (room.text, room.label, room.name) == ("Zimmer", "Zimmer", "room (Zimmer) 2.01")
    assert room.bbox == (10, 20, 30, 40) and room.page_index == 0 and room.source == "dxf"
    assert room.properties["number"] == "2.01" and room.properties["area_m2"] == 10.35
    assert room.footprint_mm == ROOM
    dim = next(e for e in indexed if e.kind == "dimension")
    assert (dim.value_mm, dim.page_index, dim.confidence) == (10800, 1, 0.7)
    assert all(e.ifc_guid for e in indexed)


def test_apartment_is_a_zone_holding_its_rooms(written: tuple) -> None:
    _, _, path = written
    f = ifcopenshell.open(str(path))
    (zone,) = f.by_type("IfcZone")
    members = [o for rel in zone.IsGroupedBy for o in rel.RelatedObjects]
    assert zone.Name == "A" and [m.is_a() for m in members] == ["IfcSpace"]


def test_standard_ifc_classes_and_quantities(written: tuple) -> None:
    _, _, path = written
    f = ifcopenshell.open(str(path))
    (wc,) = f.by_type("IfcSanitaryTerminal")
    assert wc.PredefinedType == "TOILETPAN"
    (space,) = f.by_type("IfcSpace")
    qto = next(r.RelatingPropertyDefinition for r in space.IsDefinedBy
               if r.RelatingPropertyDefinition.Name == "Qto_SpaceBaseQuantities")  # fmt: skip
    assert qto.Quantities[0].AreaValue == pytest.approx(10.35)


def test_mesh_has_room_wall_and_window(written: tuple) -> None:
    _, _, path = written
    meshes = ifc_to_mesh(path)["meshes"]
    by_class = {m["ifc_class"]: m for m in meshes}
    assert set(by_class) == {"IfcSpace", "IfcWall", "IfcWindow"}
    heights = by_class["IfcWindow"]["positions"][1::3]
    # Window extruded from 900 mm to 2100 mm -> 0.9 to 2.1 m (Y-up).
    assert (min(heights), max(heights)) == (0.9, 2.1)


def _bare(schema: str) -> ifcopenshell.file:
    f = ifcopenshell.api.project.create_file(version=schema)  # type: ignore[arg-type]
    ifcopenshell.api.root.create_entity(f, ifc_class="IfcProject", name="p")
    ifcopenshell.api.unit.assign_unit(f)
    return f


def test_nested_stairs_are_parts_not_stairs(tmp_path: Path) -> None:
    # Molio model in the dataset: 15 stairs, each an IfcStair holding riser IfcStairs.
    f = _bare("IFC4")
    stair = ifcopenshell.api.root.create_entity(f, ifc_class="IfcStair", name="S1")
    risers = [
        ifcopenshell.api.root.create_entity(f, ifc_class="IfcStair", name=f"R{i}") for i in range(3)
    ]
    ifcopenshell.api.aggregate.assign_object(f, products=risers, relating_object=stair)
    f.write(str(tmp_path / "s.ifc"))
    elements, meta = index_ifc(tmp_path / "s.ifc")
    assert sum(1 for e in elements if e.kind == "stair" and "part_of" not in e.properties) == 1
    assert meta["counts"] == {"stair": 1}


def test_ifc2x3_toilet_is_a_fixture(tmp_path: Path) -> None:
    # IFC2X3 has no IfcSanitaryTerminal: a toilet is an IfcFlowTerminal typed by
    # IfcSanitaryTerminalType. Raw entities: the authoring API needs owner history in IFC2X3.
    f = ifcopenshell.file(schema="IFC2X3")
    f.createIfcProject(ifcopenshell.guid.new(), Name="p")
    terminal = f.createIfcFlowTerminal(ifcopenshell.guid.new(), Name="WC-1")
    wc_type = f.createIfcSanitaryTerminalType(
        ifcopenshell.guid.new(), Name="WC", PredefinedType="TOILETPAN"
    )
    f.createIfcRelDefinesByType(
        ifcopenshell.guid.new(), RelatedObjects=[terminal], RelatingType=wc_type
    )
    f.write(str(tmp_path / "t.ifc"))
    elements, _ = index_ifc(tmp_path / "t.ifc")
    (wc,) = [e for e in elements if e.text == "WC-1"]
    assert wc.kind == "fixture" and wc.properties["subtype"] == "wc"
