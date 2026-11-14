"""Where an element is on its page: its own outline when known, else its label (#70).

Rooms on a drawing are found by their printed name. The reader stores the name's
box as the element's bbox and, when the room's walls close around it, the room's
outline in `properties["polygon_px"]`. A citation should show the room, so the
outline wins; the name is the fallback when no outline was found.
"""

from dataclasses import dataclass
from typing import Literal

from app.domain.geometry import BBox, Point, polygon_area

Target = Literal["element", "label"]

# Kinds whose bbox is a printed name standing for a larger area.
_LABELLED_AREAS = frozenset({"room"})


@dataclass(frozen=True)
class Extent:
    bbox: BBox | None
    polygon: tuple[Point, ...] | None
    target: Target


def element_extent(kind: str, bbox: BBox | None, properties: dict[str, object]) -> Extent:
    polygon = _polygon(properties.get("polygon_px")) if kind in _LABELLED_AREAS else None
    if polygon is not None:
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        return Extent((min(xs), min(ys), max(xs), max(ys)), polygon, "element")
    if kind in _LABELLED_AREAS and bbox is not None:
        return Extent(bbox, None, "label")  # only the printed name was found
    return Extent(bbox, None, "element")  # its own box, or located in 3D only


def _polygon(raw: object) -> tuple[Point, ...] | None:
    if not isinstance(raw, list) or len(raw) < 3:
        return None
    points: list[Point] = []
    for p in raw:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            return None
        x, y = p
        if not _is_number(x) or not _is_number(y):
            return None
        points.append((float(x), float(y)))
    return tuple(points) if polygon_area(points) > 0 else None


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)
