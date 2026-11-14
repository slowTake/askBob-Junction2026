"""No invented measurements on a sketch redraw (#82, decision 5 of the plan).

The model is told to copy only what is written. As a check that does not depend on
the model, a number it wrote is kept only when ingest's OCR also read the same digits
on the page close by. That can drop a real dimension OCR missed; it never adds one.

- Free text with any digit needs that confirmation.
- In a room name only measurement-like numbers do (with a unit, a decimal, "4x3",
  three or more digits): "Bedroom 2" keeps its number, "Bedroom 3x4m" loses "3x4m".
"""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.domain.geometry import BBox, Point
from app.domain.sketch import Plan

CONFIRM_SHARE = 0.05  # how near the word must be, as a share of the page's longer side

_UNIT = re.compile(r"\d\s*(mm|cm|m|m2|m²|ft|sq|'|\"|\u2032|\u2033)$", re.IGNORECASE)
_DECIMAL = re.compile(r"\d[.,]\d")
_BY = re.compile(r"\d\s*[x\u00d7]\s*\d", re.IGNORECASE)
# A number with what may follow it: "12 m²", "3x4m", "3,5". In the patterns \u00d7 is the
# times sign, \u2032 and \u2033 the feet and inch primes.
_NUMBER = re.compile(
    r"\d+(?:[.,]\d+)?(?:\s*[x\u00d7]\s*\d+(?:[.,]\d+)?)?(?:\s*(?:mm|cm|m²|m2|m|ft|sq|'|\"|\u2032|\u2033)(?![a-z]))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Word:
    """Text ingest read on the page, with its box in page pixels."""

    text: str
    bbox: BBox


def looks_like_measure(token: str) -> bool:
    digits = _digits(token)
    if not digits:
        return False
    return bool(
        _UNIT.search(token) or _DECIMAL.search(token) or _BY.search(token) or len(digits) >= 3
    )


def confirm_written(plan: Plan, words: Sequence[Word], width: float, height: float) -> Plan:
    reach = CONFIRM_SHARE * max(width, height)

    def confirmed(text: str, at: Point) -> bool:
        wanted = _digits(text)
        return any(_digits(w.text) == wanted and _distance(at, w.bbox) <= reach for w in words)

    notes = tuple(n for n in plan.notes if not _digits(n.text) or confirmed(n.text, n.at))
    rooms = []
    for room in plan.rooms:

        def strip(match: re.Match[str], at: Point = room.label) -> str:
            span = match.group(0)
            return "" if looks_like_measure(span) and not confirmed(span, at) else span

        name = " ".join(_NUMBER.sub(strip, room.name).split())
        if name:
            rooms.append(replace(room, name=name))
    return replace(plan, notes=notes, rooms=tuple(rooms))


def _digits(text: str) -> str:
    return "".join(c for c in text if c.isdigit())


def _distance(p: Point, box: BBox) -> float:
    dx = max(box[0] - p[0], 0.0, p[0] - box[2])
    dy = max(box[1] - p[1], 0.0, p[1] - box[3])
    return math.hypot(dx, dy)
