from app.domain.plan_rules import ROLES, plan_role, space_label


def test_roles() -> None:
    assert plan_role("IfcSpace") == "space"
    assert plan_role("IfcWallStandardCase") == "wall"
    assert plan_role("IfcSanitaryTerminal") == "fixture"
    assert plan_role("IfcSlab") is None
    assert plan_role("IfcFlowFitting") is None


def test_doors_and_windows_are_drawn_over_walls() -> None:
    assert ROLES.index("door") > ROLES.index("wall")
    assert ROLES.index("window") > ROLES.index("wall")


def test_space_label() -> None:
    assert space_label("B104", "Kitchen", 12.44) == ["Kitchen", "B104", "12.4 m²"]
    assert space_label("Kitchen", "Kitchen", None) == ["Kitchen"]
    assert space_label(None, None, None) == []
