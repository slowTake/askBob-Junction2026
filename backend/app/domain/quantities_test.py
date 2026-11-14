import pytest

from app.domain.quantities import Measured, base_quantities, total_quantity, unit_of

WALLS = [
    Measured("w1", "wall", "Grundplan", {"NetVolume": 1.5, "Length": 4.0}),
    Measured("w2", "wall", "Grundplan", {"NetVolume": 2.25, "Length": 6.0}),
    Measured("w3", "wall", "1. Sal", {"NetVolume": 4.0}),
    Measured("w4", "wall", "1. Sal", {}),  # no quantities exported for this wall
    Measured("s1", "slab", "Grundplan", {"NetVolume": 9.0}),
]


def test_total_over_every_storey() -> None:
    result = total_quantity(WALLS, "wall", "NetVolume")
    assert result.total == pytest.approx(7.75)  # 1.5 + 2.25 + 4.0; the slab is not a wall
    assert result.unit == "m3"
    assert (result.summed, result.missing) == (3, 1)  # w4 has no NetVolume
    assert result.by_storey == {"Grundplan": pytest.approx(3.75), "1. Sal": pytest.approx(4.0)}
    assert [m.element_id for m in result.listed] == ["w1", "w2", "w3"]


def test_storey_filter_ignores_case_and_spacing() -> None:
    result = total_quantity(WALLS, "wall", "NetVolume", storey=" grundplan ")
    assert result.total == pytest.approx(3.75)  # 1.5 + 2.25
    assert (result.summed, result.missing) == (2, 0)


def test_missing_counts_only_elements_the_filters_select() -> None:
    result = total_quantity(WALLS, "wall", "Length", storey="1. Sal")
    assert (result.total, result.summed, result.missing) == (0.0, 0, 2)  # w3 and w4 lack Length
    assert result.unit == "m"


def test_the_total_stays_exact_when_the_list_is_capped() -> None:
    many = [Measured(f"w{i}", "wall", "A", {"NetSideArea": 2.0}) for i in range(120)]
    result = total_quantity(many, "wall", "NetSideArea", list_max=50)
    assert result.total == pytest.approx(240.0)  # 120 x 2.0
    assert (result.summed, len(result.listed), result.unit) == (120, 50, "m2")


def test_total_is_rounded_to_a_millimetre_cube() -> None:
    thirds = [Measured(f"w{i}", "wall", None, {"NetVolume": 1 / 3}) for i in range(3)]
    assert total_quantity(thirds, "wall", "NetVolume").total == 1.0
    assert total_quantity(thirds, "wall", "NetVolume").by_storey == {}


@pytest.mark.parametrize(
    ("name", "unit"),
    [("NetVolume", "m3"), ("GrossVolume", "m3"), ("NetSideArea", "m2"), ("NetFloorArea", "m2"),
     ("GrossArea", "m2"), ("Length", "m"), ("Perimeter", "m"), ("Width", "m")],
)  # fmt: skip
def test_unit_follows_the_quantity_name(name: str, unit: str) -> None:
    assert unit_of(name) == unit


def test_unit_of_an_unknown_quantity_is_none() -> None:
    assert unit_of("GrossWeight") is None


def test_base_quantities_are_converted_to_si() -> None:
    # A wall in a millimetre model (bsc-molio: LENGTHUNIT 0.001, areas and volumes in m).
    psets: dict[str | None, dict[str, object]] = {
        "BaseQuantities": {"id": 77, "Length": 5400.0, "Width": 200.0, "NetSideArea": 14.58,
                           "NetVolume": 2.916, "GrossWeight": 6000.0},
        "ArchiCADQuantities": {"Area": 99.0, "Width": 200.0, "Volume (Net)": 2.916},
        "Pset_WallCommon": {"IsExternal": True, "Length": 1.0},
        None: {"NetVolume": 123.0},
    }  # fmt: skip
    assert base_quantities(psets, to_m=0.001, to_m2=1.0, to_m3=1.0) == {
        "Length": 5.4,  # 5,400 mm
        "Width": 0.2,
        "NetSideArea": 14.58,
        "NetVolume": 2.916,
    }


def test_qto_sets_count_and_units_scale_areas_and_volumes() -> None:
    # A model in feet: 1 ft = 0.3048 m, 1 ft² = 0.09290304 m², 1 ft³ = 0.028316846592 m³.
    psets = {"Qto_SlabBaseQuantities": {"Perimeter": 100.0, "NetArea": 200.0, "NetVolume": 50.0}}
    assert base_quantities(psets, to_m=0.3048, to_m2=0.09290304, to_m3=0.028316846592) == {
        "Perimeter": 30.48,
        "NetArea": 18.5806,  # 200 x 0.09290304 = 18.580608
        "NetVolume": 1.4158,  # 50 x 0.028316846592 = 1.4158423
    }


def test_flags_and_text_are_not_quantities() -> None:
    psets = {"BaseQuantities": {"NetVolume": True, "Length": "long", "Height": 3}}
    assert base_quantities(psets, to_m=1.0, to_m2=1.0, to_m3=1.0) == {"Height": 3.0}
