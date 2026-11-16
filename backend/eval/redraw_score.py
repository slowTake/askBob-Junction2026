"""Match a redrawn sheet's openings, rooms and texts to the truth (#131).

Each truth is found at most once, by the nearest unused redraw element within the
tolerance (greedy, nearest first). Matching is by place, never by name alone: the
benchmark has four rooms called "mh". What is then right about a found element (a door's
swing, a room's outline, a text's reading) is counted separately, so a redraw that puts
everything in the right place but reads it wrong shows as such.

Walls and ink are scored by pixels instead (`redraw_render.py`).
"""

import math
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from shapely.geometry import Polygon

from app.domain.geometry import Point
from app.domain.polygons import point_in_polygon
from eval.redraw_sheet import Opening, Room, Text

OUTLINE_IOU = 0.7  # a room's outline is right from this overlap with the truth's


@dataclass(frozen=True)
class Counts:
    predicted: int
    truth: int
    matched: int

    @property
    def precision(self) -> float:
        return self.matched / self.predicted if self.predicted else 1.0

    @property
    def recall(self) -> float:
        return self.matched / self.truth if self.truth else 1.0

    @property
    def f1(self) -> float:
        total = self.precision + self.recall
        return 2 * self.precision * self.recall / total if total else 0.0


@dataclass(frozen=True)
class OpeningScore:
    found: Counts
    swings_checked: int  # found doors whose truth says how they swing
    swings_ok: int  # ...hinged at the same end and opening into the same side


@dataclass(frozen=True)
class RoomScore:
    named: Counts  # the right name, in the right room
    outlined: int  # named, with an outline overlapping the truth's by OUTLINE_IOU


@dataclass(frozen=True)
class TextScore:
    found: Counts  # by place alone
    exact: int  # the same text (or another reading of it), ignoring spaces and case
    digits: int  # the same digits (counted only where the truth has digits)
    kind_ok: int
    rotation_ok: int


def match_openings(
    redraw: Sequence[Opening], truth: Sequence[Opening], tolerance_px: float
) -> OpeningScore:
    def cost(p: Opening, t: Opening) -> float | None:
        gap = math.dist(_middle(p.a, p.b), _middle(t.a, t.b))
        return gap if p.kind == t.kind and gap <= tolerance_px else None

    found = _pairs(redraw, truth, cost)
    checked = [(redraw[i], truth[j]) for i, j in found if truth[j].hinge and truth[j].toward]
    ok = sum(_swing_ok(p, t, tolerance_px) for p, t in checked)
    return OpeningScore(Counts(len(redraw), len(truth), len(found)), len(checked), ok)


def match_rooms(redraw: Sequence[Room], truth: Sequence[Room], tolerance_px: float) -> RoomScore:
    def cost(p: Room, t: Room) -> float | None:
        if fold(p.name) not in {fold(n) for n in (t.name, *t.alternatives)}:
            return None
        gap = math.dist(p.label, t.label)
        inside = point_in_polygon(p.label, list(t.polygon)) if t.polygon else gap <= tolerance_px
        return gap if inside else None

    named = _pairs(redraw, truth, cost)
    outlined = sum(
        1
        for i, j in named
        if (p := redraw[i].polygon) and (t := truth[j].polygon) and iou(p, t) >= OUTLINE_IOU
    )
    return RoomScore(Counts(len(redraw), len(truth), len(named)), outlined)


def match_texts(redraw: Sequence[Text], truth: Sequence[Text], tolerance_px: float) -> TextScore:
    def cost(p: Text, t: Text) -> float | None:
        gap = math.dist(p.at, t.at)
        if gap > tolerance_px:
            return None
        # A right reading wins over a nearer wrong one: wrong ones cost more than any gap.
        return gap if _reads(p, t) else gap + 2 * tolerance_px + 1

    found = [(redraw[i], truth[j]) for i, j in _pairs(redraw, truth, cost)]
    return TextScore(
        found=Counts(len(redraw), len(truth), len(found)),
        exact=sum(_reads(p, t) for p, t in found),
        digits=sum(_same_digits(p, t) for p, t in found),
        kind_ok=sum(p.kind == t.kind for p, t in found),
        rotation_ok=sum(p.rotation == t.rotation for p, t in found),
    )


def fold(name: str) -> str:
    """Lower case, single spaces, accents removed: "Keittiö" -> "keittio"."""
    decomposed = unicodedata.normalize("NFKD", " ".join(name.split()).casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def iou(a: Sequence[Point], b: Sequence[Point]) -> float:
    """Intersection over union of two outlines; a self-crossing one is repaired first."""
    pa, pb = Polygon(a).buffer(0), Polygon(b).buffer(0)
    union = pa.union(pb).area
    return pa.intersection(pb).area / union if union else 0.0


def _pairs[P, T](
    redraw: Sequence[P], truth: Sequence[T], cost: Callable[[P, T], float | None]
) -> list[tuple[int, int]]:
    """Greedy one-to-one matching, cheapest first; `cost` is None where they can't match."""
    options = sorted(
        (c, i, j)
        for i, p in enumerate(redraw)
        for j, t in enumerate(truth)
        if (c := cost(p, t)) is not None
    )
    used_p: set[int] = set()
    used_t: set[int] = set()
    pairs = []
    for _, i, j in options:
        if i not in used_p and j not in used_t:
            used_p.add(i)
            used_t.add(j)
            pairs.append((i, j))
    return pairs


def _swing_ok(redraw: Opening, truth: Opening, tolerance_px: float) -> bool:
    if not (redraw.hinge and redraw.toward and truth.hinge and truth.toward):
        return False
    same_end = math.dist(redraw.hinge, truth.hinge) <= tolerance_px
    return same_end and _side(truth, redraw.toward) == _side(truth, truth.toward)


def _side(wall: Opening, p: Point) -> int:
    """Which side of the opening's line `p` is on: 1, -1, or 0 on the line."""
    (ax, ay), (bx, by) = wall.a, wall.b
    cross = (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)
    return (cross > 0) - (cross < 0)


def _middle(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _reads(redraw: Text, truth: Text) -> bool:
    """The redraw gives the truth's text or one of its other readings."""
    return any(_same(redraw.text, t) for t in (truth.text, *truth.alternatives))


def _same_digits(redraw: Text, truth: Text) -> bool:
    readings = [d for t in (truth.text, *truth.alternatives) if (d := _digits(t))]
    return _digits(redraw.text) in readings


def _same(a: str, b: str) -> bool:
    return "".join(a.split()).casefold() == "".join(b.split()).casefold()


def _digits(text: str) -> str:
    return "".join(c for c in text if c.isdigit())
