from app.domain.model_rules import (
    extrusion_for,
    ifc_target,
    marked_kind,
    sanitary_subtype,
)


def test_building_elements_use_their_ifc_classes() -> None:
    assert ifc_target("room") == ("IfcSpace", None, None)
    assert ifc_target("door") == ("IfcDoor", None, None)
    assert ifc_target("unit") == ("IfcZone", None, None)


def test_known_fixtures_get_standard_sanitary_types() -> None:
    # IFC4 IfcSanitaryTerminalTypeEnum: TOILETPAN, WASHHANDBASIN, SHOWER, BATH, SINK.
    assert ifc_target("fixture", "wc") == ("IfcSanitaryTerminal", "TOILETPAN", None)
    assert ifc_target("fixture", "bathtub") == ("IfcSanitaryTerminal", "BATH", None)


def test_unknown_fixture_and_other_kinds_are_marked_proxies() -> None:
    assert ifc_target("fixture") == ("IfcBuildingElementProxy", None, "bob:fixture")
    assert ifc_target("fixture", "stove") == ("IfcBuildingElementProxy", None, "bob:fixture")


def test_text_findings_are_annotations() -> None:
    assert ifc_target("dimension") == ("IfcAnnotation", None, "bob:dimension")
    assert ifc_target("room_number") == ("IfcAnnotation", None, "bob:room_number")
    assert ifc_target("height") == ("IfcAnnotation", None, "bob:height")  # "h1600" (#36)


def test_round_trip_of_marks_and_sanitary_types() -> None:
    for kind in ("dimension", "text", "fixture", "scale"):
        assert marked_kind(ifc_target(kind)[2]) == kind
    assert marked_kind("Basic Wall:200mm") is None
    assert marked_kind(None) is None
    assert sanitary_subtype("TOILETPAN") == "wc"
    assert sanitary_subtype("NOTDEFINED") is None


def test_extrusions() -> None:
    # Windows sit 900 mm above the floor and are 1200 mm tall (900 + 1200 = 2100 mm head).
    assert extrusion_for("window") == (900.0, 1200.0)
    assert extrusion_for("text") is None
