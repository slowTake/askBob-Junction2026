"""Net floor area rules, as used by the Swiss dwellings answer key.

Net area = sum of numbered rooms that are neither shafts nor outdoor. A shaft is
an unnamed outline narrower than SHAFT_MAX_WIDTH_M (unnamed wide rooms, e.g.
unlabelled bathrooms, still count). Balconies, loggias and terraces are outdoor.
"""

from dataclasses import dataclass

from app.domain.geometry import Point, polygon_area

SHAFT_MAX_WIDTH_M = 0.55


@dataclass(frozen=True)
class RoomArea:
    element_id: str
    number: str | None
    name: str | None  # the printed label, e.g. "Pièce"
    unit: str | None  # apartment id, e.g. "A"
    area_m2: float
    outdoor: bool
    shaft: bool = False


def mean_width(polygon: list[Point]) -> float:
    """Average width of a shape: area / half its perimeter (exact wh/(w+h) for rectangles)."""
    n = len(polygon)
    perimeter = sum(
        (
            (polygon[(i + 1) % n][0] - polygon[i][0]) ** 2
            + (polygon[(i + 1) % n][1] - polygon[i][1]) ** 2
        )
        ** 0.5
        for i in range(n)
    )
    return polygon_area(polygon) / (perimeter / 2) if perimeter else 0.0


def is_shaft(name: str | None, width_m: float) -> bool:
    return not name and width_m < SHAFT_MAX_WIDTH_M


def is_net_room(room: RoomArea) -> bool:
    return bool(room.number) and not room.shaft and not room.outdoor


def net_area(
    rooms: list[RoomArea], unit: str | None = None, name: str | None = None
) -> tuple[float, list[RoomArea]]:
    """Total net area (m², 2 decimals) and the rooms counted, optionally filtered.

    Filtering by `name` counts every room with that label (also outdoor ones),
    because "all rooms labelled 'Balcon'" means exactly those rooms.
    """
    if name is not None:
        picked = [r for r in rooms if r.name == name]
    else:
        picked = [r for r in rooms if is_net_room(r)]
    if unit is not None:
        picked = [r for r in picked if r.unit == unit]
    return round(sum(r.area_m2 for r in picked), 2), picked


OUTLINE_TOLERANCE = 0.15


def outline_agrees(traced_m2: float, printed_m2: float | None) -> bool:
    """A traced room outline is trusted only if it matches the printed area (when there is one)."""
    if printed_m2 is None or printed_m2 <= 0:
        return True
    return abs(traced_m2 - printed_m2) <= OUTLINE_TOLERANCE * printed_m2
