import pytest

from app.domain.areas import RoomArea, is_shaft, mean_width, net_area, outline_agrees

# Apartment B of site2150_bldg3001_floor13690 (dataset answer: 37.6 m²).
ROOMS = [
    RoomArea("a", "2.09", "Pièce", "B", 17.6, False),
    RoomArea("b", "2.10", "Cuisine", "B", 8.18, False),
    RoomArea("c", "2.11", "Couloir", "B", 7.52, False),
    RoomArea("d", "2.12", None, "B", 2.25, False, shaft=True),  # 0.51 m wide, unnamed
    RoomArea("e", "2.13", "Bain", "B", 4.3, False),
    RoomArea("f", "2.30", "Balcon", "B", 6.0, True),  # outdoor
    RoomArea("g", "2.14", "Cuisine", "C", 8.32, False),
]


def test_apartment_net_area_skips_shafts_and_outdoor() -> None:
    total, counted = net_area(ROOMS, unit="B")
    # 17.6 + 8.18 + 7.52 + 4.3 = 37.6, the dataset's answer.
    assert total == pytest.approx(37.6)
    assert [r.number for r in counted] == ["2.09", "2.10", "2.11", "2.13"]


def test_floor_net_area() -> None:
    total, _ = net_area(ROOMS)
    assert total == pytest.approx(37.6 + 8.32)


def test_by_label_includes_outdoor_when_asked_by_name() -> None:
    assert net_area(ROOMS, name="Cuisine")[0] == pytest.approx(8.18 + 8.32)
    assert net_area(ROOMS, name="Balcon")[0] == pytest.approx(6.0)


def test_mean_width_of_rectangles() -> None:
    # Rectangle w x h: area / (perimeter / 2) = wh / (w + h).
    # 0.5 x 3.13 m shaft -> 1.565 / 3.63 = 0.431 m; 2.8 x 1.6 m bathroom -> 4.48 / 4.4 = 1.018 m.
    shaft = [(0.0, 0.0), (0.5, 0.0), (0.5, 3.13), (0.0, 3.13)]
    bath = [(0.0, 0.0), (2.8, 0.0), (2.8, 1.6), (0.0, 1.6)]
    assert mean_width(shaft) == pytest.approx(0.431, abs=1e-3)
    assert mean_width(bath) == pytest.approx(1.018, abs=1e-3)


def test_shaft_needs_both_no_name_and_narrow() -> None:
    assert is_shaft(None, width_m=0.43)
    assert not is_shaft(None, width_m=1.02)  # unlabelled bathroom: counts
    assert not is_shaft("Réduit", width_m=0.43)  # a named narrow storage room counts


def test_unnamed_wide_room_counts_in_net_area() -> None:
    rooms = [
        RoomArea("x", "2.04", None, "A", 3.38, False),
        RoomArea("y", "2.05", None, "A", 1.55, False, shaft=True),
    ]
    assert net_area(rooms, unit="A")[0] == pytest.approx(3.38)


def test_traced_outline_must_agree_with_printed_area() -> None:
    # 15 % tolerance: 15.61 printed vs 14.0 traced is a 10.3 % gap (kept);
    # vs 120.0 traced, the fill leaked through a door (rejected).
    assert outline_agrees(traced_m2=14.0, printed_m2=15.61)
    assert not outline_agrees(traced_m2=120.0, printed_m2=15.61)
    assert outline_agrees(traced_m2=9.0, printed_m2=None)  # nothing to check against
