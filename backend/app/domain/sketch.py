"""The sketch redraw (#82): a model authors the whole plan of a hand-drawn page.

On raster image pages ingest's OCR and line detection are the unreliable part, so a
model draws the plan from the photo, checks its own rendered draft against it and
corrects it. These functions read its answer and keep the bookkeeping; nothing here
calls the model, reads the clock or touches the database.

- Coordinates in an answer are pixels of the image as sent (origin top left, y down).
- An entry that is malformed, off the image or of zero length is skipped, never repaired.
- Nothing gets a real-world length: no scale, no areas. Text is only what is written.
"""

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import TypeVar, cast

from app.domain.geometry import Point
from app.domain.upscale import UPSCALE_FORMAT

SKETCH_SOURCE = "sketch"  # Element.source of everything the redraw stores
SKETCH_MODE = "sketch"  # page.meta["upscale"]["mode"]
SKETCH_CONFIDENCE = 0.8  # read from a hand drawing by a model: never exact
SKETCH_KINDS = frozenset({"image"})  # Document.kind that can be a sketch (redraw_mode.py)
MIN_LENGTH_PX = 1.0
MAX_ENTRIES = 400  # per list; a floor plan has far fewer

T = TypeVar("T")


@dataclass(frozen=True)
class Wall:
    a: Point
    b: Point
    outer: bool  # thickness class: outer walls are drawn thicker


@dataclass(frozen=True)
class Door:
    a: Point  # the opening, both ends on the wall
    b: Point
    hinge_at_a: bool
    toward: Point  # any point on the side the leaf opens to


@dataclass(frozen=True)
class Window:
    a: Point
    b: Point


@dataclass(frozen=True)
class Room:
    name: str  # exactly as written
    label: Point
    outline: tuple[Point, ...] | None


@dataclass(frozen=True)
class Note:
    """Text literally written on the sketch, other than a room name."""

    text: str
    at: Point


@dataclass(frozen=True)
class Plan:
    walls: tuple[Wall, ...] = ()
    doors: tuple[Door, ...] = ()
    windows: tuple[Window, ...] = ()
    rooms: tuple[Room, ...] = ()
    notes: tuple[Note, ...] = ()


def says_matches(raw: object) -> bool:
    """The model said its draft matches the sketch (a plain JSON true, nothing else)."""
    return isinstance(raw, Mapping) and raw.get("matches") is True


def parse_plan(raw: object, width: float, height: float) -> Plan:
    """Read a plan in pixels of a `width` x `height` image.

    Raises ValueError when the answer has no plan lists at all.
    """
    if not isinstance(raw, Mapping):
        raise ValueError("the answer is not an object")
    lists = {key: raw.get(key) for key in ("walls", "doors", "windows", "rooms", "texts")}
    if not all(isinstance(v, list) for v in lists.values()):
        raise ValueError("the answer has no plan lists")

    def read(key: str, parse: Callable[[object, float, float], T | None]) -> tuple[T, ...]:
        entries = cast(list[object], lists[key])[:MAX_ENTRIES]
        found = (parse(e, width, height) for e in entries)
        return tuple(f for f in found if f is not None)

    return Plan(
        walls=read("walls", _wall),
        doors=read("doors", _door),
        windows=read("windows", _window),
        rooms=read("rooms", _room),
        notes=read("texts", _note),
    )


def scale_plan(plan: Plan, factor: float) -> Plan:
    """Every point multiplied by `factor` (image pixels <-> page pixels)."""

    def p(point: Point) -> Point:
        return (point[0] * factor, point[1] * factor)

    return Plan(
        walls=tuple(replace(w, a=p(w.a), b=p(w.b)) for w in plan.walls),
        doors=tuple(replace(d, a=p(d.a), b=p(d.b), toward=p(d.toward)) for d in plan.doors),
        windows=tuple(replace(w, a=p(w.a), b=p(w.b)) for w in plan.windows),
        rooms=tuple(
            replace(
                r,
                label=p(r.label),
                outline=tuple(p(q) for q in r.outline) if r.outline else None,
            )
            for r in plan.rooms
        ),
        notes=tuple(replace(n, at=p(n.at)) for n in plan.notes),
    )


def plan_json(plan: Plan) -> dict[str, list[dict[str, object]]]:
    """The plan in the answer schema again, to show the model its current draft."""

    def ends(a: Point, b: Point) -> dict[str, object]:
        return {"x0": _r(a[0]), "y0": _r(a[1]), "x1": _r(b[0]), "y1": _r(b[1])}

    return {
        "walls": [{**ends(w.a, w.b), "outer": w.outer} for w in plan.walls],
        "doors": [
            {
                **ends(d.a, d.b),
                "hinge": "start" if d.hinge_at_a else "end",
                "opens_toward_x": _r(d.toward[0]),
                "opens_toward_y": _r(d.toward[1]),
            }
            for d in plan.doors
        ],
        "windows": [ends(w.a, w.b) for w in plan.windows],
        "rooms": [
            {
                "name": r.name,
                "x": _r(r.label[0]),
                "y": _r(r.label[1]),
                "outline": [{"x": _r(x), "y": _r(y)} for x, y in r.outline or ()],
            }
            for r in plan.rooms
        ],
        "texts": [{"text": n.text, "x": _r(n.at[0]), "y": _r(n.at[1])} for n in plan.notes],
    }


def sketch_cache_entry(
    document_version: int,
    model: str,
    added: int,
    *,
    rounds: int,
    matched: bool,
    input_tokens: int,
    output_tokens: int,
) -> dict[str, object]:
    """What a page's meta keeps under "upscale" once the sketch redraw has run."""
    return {
        "document_version": document_version,
        "format": UPSCALE_FORMAT,
        "mode": SKETCH_MODE,
        "model": model,
        "added": added,
        "rounds": rounds,
        "matched": matched,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def claim_is_live(claim: object, now_s: float, stale_after_s: float) -> bool:
    """A redraw of this page is running (claimed less than `stale_after_s` ago).

    A claim older than that belongs to a run that died without clearing it.
    """
    if not isinstance(claim, Mapping):
        return False
    started = _number(claim.get("started_s"))
    return started is not None and now_s - started < stale_after_s


# --- reading one entry ----------------------------------------------------------


def _wall(entry: object, width: float, height: float) -> Wall | None:
    ends = _segment(entry, width, height)
    if ends is None or not isinstance(entry, Mapping) or not isinstance(entry.get("outer"), bool):
        return None
    return Wall(ends[0], ends[1], outer=bool(entry["outer"]))


def _door(entry: object, width: float, height: float) -> Door | None:
    ends = _segment(entry, width, height)
    if ends is None or not isinstance(entry, Mapping) or entry.get("hinge") not in ("start", "end"):
        return None
    toward = _point(entry, "opens_toward_x", "opens_toward_y", width, height)
    if toward is None:
        return None
    a, b = ends
    side = (b[0] - a[0]) * (toward[1] - a[1]) - (b[1] - a[1]) * (toward[0] - a[0])
    if abs(side) < 1e-9:
        return None  # on the door's own line: no side
    return Door(a, b, hinge_at_a=entry["hinge"] == "start", toward=toward)


def _window(entry: object, width: float, height: float) -> Window | None:
    ends = _segment(entry, width, height)
    return Window(*ends) if ends else None


def _room(entry: object, width: float, height: float) -> Room | None:
    if not isinstance(entry, Mapping):
        return None
    name = _text(entry.get("name"))
    label = _point(entry, "x", "y", width, height)
    if name is None or label is None:
        return None
    raw = entry.get("outline")
    points = [_point(q, "x", "y", width, height) for q in raw] if isinstance(raw, list) else []
    outline = None
    if len(points) >= 3 and all(q is not None for q in points):
        outline = tuple(q for q in points if q is not None)
    return Room(name, label, outline)


def _note(entry: object, width: float, height: float) -> Note | None:
    if not isinstance(entry, Mapping):
        return None
    text = _text(entry.get("text"))
    at = _point(entry, "x", "y", width, height)
    return Note(text, at) if text is not None and at is not None else None


def _segment(entry: object, width: float, height: float) -> tuple[Point, Point] | None:
    a = _point(entry, "x0", "y0", width, height)
    b = _point(entry, "x1", "y1", width, height)
    if a is None or b is None or math.dist(a, b) < MIN_LENGTH_PX:
        return None
    return a, b


def _point(entry: object, kx: str, ky: str, width: float, height: float) -> Point | None:
    if not isinstance(entry, Mapping):
        return None
    x, y = _number(entry.get(kx)), _number(entry.get(ky))
    if x is None or y is None or not (0 <= x <= width and 0 <= y <= height):
        return None
    return (x, y)


def _text(v: object) -> str | None:
    return v.strip() if isinstance(v, str) and v.strip() else None


def _number(v: object) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def _r(v: float) -> float:
    return round(v, 1)
