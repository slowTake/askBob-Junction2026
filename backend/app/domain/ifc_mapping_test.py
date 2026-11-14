from typing import Any

from app.domain.ifc_mapping import flatten_psets, ifc_kind, zup_to_yup


def test_ifc_kind() -> None:
    assert ifc_kind("IfcSpace") == "room"
    assert ifc_kind("IfcWallStandardCase") == "wall"
    assert ifc_kind("IfcFlowTerminal") == "element"


def test_flatten_drops_ids_and_non_scalars() -> None:
    psets = {"Pset_WallCommon": {"id": 7, "IsExternal": True, "Layers": [1, 2]}}
    assert flatten_psets(psets) == {"Pset_WallCommon.IsExternal": True}


def test_flatten_is_sorted_and_limited() -> None:
    psets = {"B": {"y": 1, "x": 2}, "A": {"z": 3}}
    assert list(flatten_psets(psets)) == ["A.z", "B.x", "B.y"]
    assert list(flatten_psets(psets, limit=2)) == ["A.z", "B.x"]


def test_flatten_keeps_a_pset_with_no_name() -> None:
    # hitos_arc.ifc: ifcopenshell returns quantity sets with no Name under a None key.
    psets: dict[str | None, dict[str, Any]] = {
        None: {"id": 1, "NetVolume": 0.27},
        "Pset_BeamCommon": {"IsExternal": False},
    }
    assert flatten_psets(psets) == {
        "Pset_BeamCommon.IsExternal": False,
        "Unnamed.NetVolume": 0.27,
    }


def test_zup_to_yup() -> None:
    # (1, 2, 3) in IFC (z up) is (1, 3, -2) in three.js (y up).
    assert zup_to_yup([1.0, 2.0, 3.0, 0.0, 0.0, 0.0]) == [1.0, 3.0, -2.0, 0.0, 0.0, 0.0]


def test_flatten_survives_unnamed_property_sets() -> None:
    # data/ifc_bench/hitos_arc.ifc has property sets whose Name is null.
    psets: dict[str | None, dict[str, object]] = {None: {"Fire": "EI60"}, "Pset_A": {"x": 1}}
    assert flatten_psets(psets) == {"Pset_A.x": 1, "Unnamed.Fire": "EI60"}
