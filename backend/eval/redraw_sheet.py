"""A redrawn sheet as the redraw benchmark scores it, and the truth file that holds one (#131).

The truth is written by hand from the benchmark image, in coordinates normalised to
the page (0..1 of its width and of its height), so it does not depend on the image's
size. `load_sheet` turns it into page pixels. The app's redraw is turned into the same
shapes, so both sides are scored by one set of functions (`redraw_score.py`).

A wall is given as its centre line with a thickness (a share of the page width) or as
its outline. A malformed entry is refused, never repaired: a truth file is checked by
eye once and must say exactly what was meant. What its author could not be sure of is
said too: `"uncertain": true` on any entry, and `"alternatives"` on a text or room name
for the other readings a person could not rule out (which also makes it uncertain).
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.geometry import Point

OPENING_KINDS = ("door", "window")
TEXT_KINDS = ("dimension", "height", "other")  # room names are scored as rooms
ROTATIONS = (0, 90)


@dataclass(frozen=True)
class Wall:
    polygon: tuple[Point, ...]
    uncertain: bool = False  # the truth's author could not be sure it is there


@dataclass(frozen=True)
class Opening:
    kind: str  # "door" or "window"
    a: Point  # the gap on its wall, end to end
    b: Point
    hinge: Point | None = None  # a door: the end its leaf turns on
    toward: Point | None = None  # a door: a point in the room it opens into
    uncertain: bool = False
    frame: tuple[Point, ...] | None = None  # a window's frame as drawn (redraw only, D-055)


@dataclass(frozen=True)
class Room:
    name: str  # as written on the drawing
    label: Point  # the middle of the written name
    polygon: tuple[Point, ...] | None = None
    alternatives: tuple[str, ...] = ()  # other readings a person could not rule out
    uncertain: bool = False


@dataclass(frozen=True)
class Text:
    text: str  # as written, decimal comma kept
    kind: str
    at: Point
    rotation: int = 0  # degrees: 0 reads left to right, 90 bottom to top
    alternatives: tuple[str, ...] = ()
    uncertain: bool = False


@dataclass(frozen=True)
class Fixture:
    polygon: tuple[Point, ...]  # the outline drawn (redraw only, #146: the truth has none)


@dataclass(frozen=True)
class Sheet:
    walls: tuple[Wall, ...] = ()
    openings: tuple[Opening, ...] = ()
    rooms: tuple[Room, ...] = ()
    texts: tuple[Text, ...] = ()
    fixtures: tuple[Fixture, ...] = ()


def load_sheet(raw: object, width: float, height: float) -> Sheet:
    """A truth file's JSON, in page pixels. Raises ValueError when anything is malformed."""
    if not isinstance(raw, Mapping):
        raise ValueError("a sheet is an object")

    def point(v: object) -> Point:
        if not isinstance(v, list) or len(v) != 2:
            raise ValueError(f"not a point: {v!r}")
        x, y = (_share(c) for c in v)
        return (x * width, y * height)

    def polygon(v: object) -> tuple[Point, ...]:
        if not isinstance(v, list) or len(v) < 3:
            raise ValueError("a polygon needs three points")
        return tuple(point(p) for p in v)

    def wall(e: Mapping[str, object]) -> Wall:
        if "polygon" in e:
            return Wall(polygon(e["polygon"]), _flag(e))
        thickness = _share(e.get("thickness"))
        if thickness <= 0:
            raise ValueError("a wall needs a thickness")
        return Wall(band(point(e.get("a")), point(e.get("b")), thickness * width), _flag(e))

    def opening(e: Mapping[str, object]) -> Opening:
        kind = e.get("kind")
        if kind not in OPENING_KINDS:
            raise ValueError(f"not an opening kind: {kind!r}")
        a, b = point(e.get("a")), point(e.get("b"))
        end = e.get("hinge")
        if end not in (None, "a", "b"):
            raise ValueError("a hinge is 'a' or 'b'")
        hinge = a if end == "a" else b if end == "b" else None
        toward = point(e["toward"]) if e.get("toward") is not None else None
        return Opening(str(kind), a, b, hinge, toward, _flag(e))

    def room(e: Mapping[str, object]) -> Room:
        outline = polygon(e["polygon"]) if e.get("polygon") is not None else None
        others = _alternatives(e)
        name, label = _text(e.get("name")), point(e.get("label"))
        return Room(name, label, outline, others, bool(others) or _flag(e))

    def text(e: Mapping[str, object]) -> Text:
        kind, rotation = e.get("kind"), e.get("rotation", 0)
        if kind not in TEXT_KINDS:
            raise ValueError(f"not a text kind: {kind!r}")
        if rotation not in ROTATIONS or isinstance(rotation, bool):
            raise ValueError(f"not a rotation: {rotation!r}")
        others = _alternatives(e)
        return Text(
            _text(e.get("text")),
            str(kind),
            point(e.get("at")),
            int(str(rotation)),
            others,
            bool(others) or _flag(e),
        )

    return Sheet(
        tuple(wall(e) for e in _entries(raw, "walls")),
        tuple(opening(e) for e in _entries(raw, "openings")),
        tuple(room(e) for e in _entries(raw, "rooms")),
        tuple(text(e) for e in _entries(raw, "texts")),
    )


def band(a: Point, b: Point, thickness: float) -> tuple[Point, ...]:
    """The outline of a wall drawn along a-b, `thickness` wide, running half of it past each end.

    The square ends fill the corner where two runs meet at a shared end point.
    """
    length = math.dist(a, b)
    if length == 0:
        raise ValueError("a wall needs a length")
    h = thickness / 2
    dx, dy = (b[0] - a[0]) / length * h, (b[1] - a[1]) / length * h
    nx, ny = -dy, dx
    a0, b0 = (a[0] - dx, a[1] - dy), (b[0] + dx, b[1] + dy)
    return (
        (a0[0] + nx, a0[1] + ny),
        (b0[0] + nx, b0[1] + ny),
        (b0[0] - nx, b0[1] - ny),
        (a0[0] - nx, a0[1] - ny),
    )


def _entries(raw: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    entries = raw.get(key, [])
    if not isinstance(entries, list) or not all(isinstance(e, Mapping) for e in entries):
        raise ValueError(f"{key} is a list of objects")
    return entries


def _share(v: object) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
        raise ValueError(f"not a share of the page: {v!r}")
    return float(v)


def _flag(e: Mapping[str, object]) -> bool:
    v = e.get("uncertain", False)
    if not isinstance(v, bool):
        raise ValueError(f"uncertain is true or false: {v!r}")
    return v


def _alternatives(e: Mapping[str, object]) -> tuple[str, ...]:
    """Other readings; giving any makes the entry uncertain."""
    v = e.get("alternatives", [])
    if not isinstance(v, list):
        raise ValueError("alternatives is a list of texts")
    return tuple(_text(a) for a in v)


def _text(v: object) -> str:
    if isinstance(v, str) and v.strip():
        return v.strip()
    raise ValueError(f"not a text: {v!r}")
