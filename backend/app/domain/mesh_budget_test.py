from app.domain.mesh_budget import tier, within_budget


def test_tiers() -> None:
    assert tier("IfcWall") == 0
    assert tier("IfcSanitaryTerminal") == 1
    assert tier("IfcFlowSegment") == 2
    assert tier("IfcFlowFitting") == 3


def test_everything_fits() -> None:
    assert within_budget([("IfcWall", 10), ("IfcFlowFitting", 10)], limit=100) == [0, 1]


def test_fabric_wins_over_fittings() -> None:
    meshes = [("IfcFlowFitting", 60), ("IfcWall", 50), ("IfcDoor", 30), ("IfcFlowTerminal", 15)]
    # Wall 50 + door 30 = 80; terminal 15 -> 95; the 60-triangle fitting no longer fits in 100.
    assert within_budget(meshes, limit=100) == [1, 2, 3]


def test_a_too_big_mesh_does_not_block_smaller_ones() -> None:
    meshes = [("IfcWall", 500), ("IfcWall", 40), ("IfcSlab", 40)]
    assert within_budget(meshes, limit=100) == [1, 2]
