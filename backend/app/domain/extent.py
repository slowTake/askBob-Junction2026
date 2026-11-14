"""Where an element is on its page: its own outline when known, else its label (#70).

Rooms on a drawing are found by their printed name. The reader stores the name's
box as the element's bbox and, when the room's walls close around it, the room's
outline in `properties["polygon_px"]`. A citation should show the room, so the
outline wins; the name is the fallback when no outline was found.
"""

from dataclasses import dataclass
from typing import Literal

from app.domain.geometry import BBox, Point

Target = Literal["element", "label"]

# Kinds whose bbox is a printed name standing for a larger area.
_LABELLED_AREAS = frozenset({"room"})


@dataclass(frozen=True)
class Extent:
    bbox: BBox | None
    polygon: tuple[Point, ...] | None
    target: Target


def element_extent(kind: str, bbox: BBox | None, properties: dict[str, object]) -> Extent:
    if kind not in _LABELLED_AREAS:
        return Extent(bbox, None, "element")
    polygon = _polygon(properties.get("polygon_px"))
    if polygon is None:
        return Extent(bbox, None, "label")
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return Extent((min(xs), min(ys), max(xs), max(ys)), polygon, "element")


def _polygon(raw: object) -> tuple[Point, ...] | None:
    if not isinstance(raw, list) or len(raw) < 3:
        return None
    points: list[Point] = []
    for p in raw:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            return None
        x, y = p
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return None
        points.append((x, y))
    return tuple(points)
