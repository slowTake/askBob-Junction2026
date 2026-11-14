"""What the floor-plan model's output means for our building model (D-022).

The `vision` service returns named polygons in page pixels:
    {"rooms": [{"class", "polygon"}], "walls": [polygon], "objects": [{"class", "polygon"}]}
These functions turn them into findings with our kinds and fixture subtypes. They
are pure: the reader adds boxes, millimetre footprints and OCR labels.
"""

from dataclasses import dataclass, field
from typing import Any

from app.domain.geometry import Point, polygon_area
from app.domain.polygons import point_in_polygon

OBJECT_CONFIDENCE = 0.7  # doors, windows, fixtures: right most of the time, checkable
ROOM_CONFIDENCE = 0.5  # a model room without a printed name: the type is a guess
WALL_CONFIDENCE = 0.6

# Model object class -> (our kind, fixture subtype). Sinks are decided by the room.
_OBJECTS: dict[str, tuple[str, str | None]] = {
    "Door": ("door", None),
    "Window": ("window", None),
    "Toilet": ("fixture", "wc"),
    "Bathtub": ("fixture", "bathtub"),
    "Sink": ("fixture", "washbasin"),
    "Closet": ("fixture", None),
    "Electrical Appliance": ("fixture", None),
    "Sauna Bench": ("fixture", None),
    "Fire Place": ("fixture", None),
    "Chimney": ("fixture", None),
}
# Model room class -> (our room category, outdoor). Undefined rooms aren't named.
_ROOMS: dict[str, tuple[str, bool]] = {
    "Kitchen": ("kitchen", False),
    "Living Room": ("living room", False),
    "Bed Room": ("bedroom", False),
    "Bath": ("bathroom", False),
    "Entry": ("corridor", False),
    "Storage": ("storage", False),
    "Garage": ("garage", False),
    "Outdoor": ("outdoor", True),
}


@dataclass(frozen=True)
class Shape:
    cls: str
    polygon: list[Point]


@dataclass
class Parsed:
    rooms: list[Shape] = field(default_factory=list)
    walls: list[list[Point]] = field(default_factory=list)
    objects: list[Shape] = field(default_factory=list)


@dataclass
class Finding:
    kind: str
    polygon: list[Point]
    properties: dict[str, Any]
    confidence: float


def parse(result: Any) -> Parsed:
    """Keep only well-formed entries: known classes, polygons of numeric points."""
    out = Parsed()
    if not isinstance(result, dict):
        return out
    for item in _items(result.get("rooms")):
        polygon = _polygon(item.get("polygon"), 3)
        if polygon and item.get("class") in _ROOMS | {"Undefined": ("", False)}:
            out.rooms.append(Shape(item["class"], polygon))
    for raw in _items(result.get("walls"), dicts=False):
        polygon = _polygon(raw, 3)
        if polygon:
            out.walls.append(polygon)
    for item in _items(result.get("objects")):
        polygon = _polygon(item.get("polygon"), 2)
        if polygon and item.get("class") in _OBJECTS:
            out.objects.append(Shape(item["class"], polygon))
    return out


def object_findings(parsed: Parsed) -> list[Finding]:
    """Doors, windows and fixtures. A sink inside a kitchen is a sink, else a washbasin."""
    kitchens = [r.polygon for r in parsed.rooms if r.cls == "Kitchen"]
    found = []
    for obj in parsed.objects:
        kind, subtype = _OBJECTS[obj.cls]
        if obj.cls == "Sink" and any(point_in_polygon(_centre(obj.polygon), k) for k in kitchens):
            subtype = "sink"
        properties: dict[str, Any] = {"model_class": obj.cls}
        if subtype:
            properties["subtype"] = subtype
        elif kind == "fixture":
            properties["object"] = obj.cls.lower()
        found.append(Finding(kind, obj.polygon, properties, OBJECT_CONFIDENCE))
    return found


def wall_findings(parsed: Parsed) -> list[Finding]:
    return [Finding("wall", w, {}, WALL_CONFIDENCE) for w in parsed.walls]


def outline_for(point: Point, rooms: list[Shape]) -> list[Point] | None:
    """The smallest model room around a printed room label, if any."""
    around = [r.polygon for r in rooms if point_in_polygon(point, r.polygon)]
    return min(around, key=polygon_area) if around else None


def unlabelled_rooms(
    rooms: list[Shape], label_points: list[Point], min_area_px: float
) -> list[Finding]:
    """Model rooms that no printed label names; typed by the model, Undefined skipped."""
    found = []
    for room in rooms:
        if room.cls not in _ROOMS or polygon_area(room.polygon) < min_area_px:
            continue
        if any(point_in_polygon(p, room.polygon) for p in label_points):
            continue
        category, outdoor = _ROOMS[room.cls]
        properties: dict[str, Any] = {"category": category, "model_class": room.cls}
        if outdoor:
            properties["outdoor"] = True
        found.append(Finding("room", room.polygon, properties, ROOM_CONFIDENCE))
    return found


def long_side_px(polygon: list[Point]) -> float:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return max(max(xs) - min(xs), max(ys) - min(ys))


def _centre(polygon: list[Point]) -> Point:
    return (sum(p[0] for p in polygon) / len(polygon), sum(p[1] for p in polygon) / len(polygon))


def _items(value: Any, dicts: bool = True) -> list[Any]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, dict) == dicts]


def _polygon(value: Any, min_points: int) -> list[Point] | None:
    if not isinstance(value, list) or len(value) < min_points:
        return None
    points: list[Point] = []
    for p in value:
        if not (isinstance(p, list | tuple) and len(p) == 2):
            return None
        if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in p):
            return None
        points.append((float(p[0]), float(p[1])))
    return points
