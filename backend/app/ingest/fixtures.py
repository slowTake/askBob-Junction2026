"""Fixtures read from a raster page's ink: tables, chairs, basins, WC bowls, cupboards (#146).

A fixture symbol is drawn as nested thin outlines a few px apart. The band tracing
(D-053) closes them into bands, so they were traced as wall pieces, and a burner's or a
basin's circle could read as a door's arc. They are found here by the small hole each
one closes round, read on the ink itself: the band mask's rings are split open.

A hole is a fixture's inside when it is small (about 0.5 m on colorful-34), not a strip
(a double line's gap), its rim is thin lines (a chimney's is thick), the first trace
closed that rim into a band (that is what made it false wall), it borders one room (a
closet's walls border several), it is not lettering, and it fills its box. The fixture's
ink is the thin ink within `REACH_PX` of the hole, never thick ink or a thin-line wall:
that is carved out of the wall trace, and a fixture closed by itself (a burner, not a
chair against a wall) also out of the door scan. Pure: masks in, polygons out.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np
from scipy import ndimage

from app.domain.geometry import BBox, Point
from app.ingest.doors import Door, arc_angles
from app.ingest.rooms import Mask
from app.ingest.wall_trace import band_mask, box_mask

SIDE_SHARE = 0.045  # a hole at most this share of the page's longest side: 22 px, 0.5 m
MIN_SIDE_PX = 4  # a letter's loop or a hatch cell is smaller
MIN_AREA_PX = 16
STRIP_PX = 6  # a hole this thin and STRIP_ASPECT times longer is a double line's gap
STRIP_ASPECT = 2.5
RIM_THICK = 0.6  # at most this share of the rim is thick ink: a chimney is thick all round
RIM_BAND = 0.5  # at least this share of the rim was closed into a band
NEIGHBOUR_PX = 5  # the regions round the hole, read this far out
NEIGHBOUR_TIMES = 2  # count when this many times the hole: a chair beside the table does not
MAX_NEIGHBOURS = 1  # a fixture sits in one room
TEXT_SHARE = 0.5  # a hole more than this inside word boxes is a letter's
FILL_CLOSE_PX = 5  # strokes inside the hole are closed over before its fill is read
MIN_FILL = 0.6  # of its box: an oval 0.78, a rectangle more, a letter's L-shaped gap less
SWING_SHARE = 0.5  # a hole this much inside a found door's quarter disc is its swing
SWING_MARGIN_PX = 2
REACH_PX = 3  # the fixture's own outlines lie this close to its hole (nested outlines)
SELF_CLOSED = 0.25  # at most this share of the rim on a traced wall: closed by itself
POLYGON_EPSILON = 1.0

_EIGHT = np.ones((3, 3), np.uint8)


@dataclass(frozen=True)
class Fixture:
    polygon: list[Point]  # page px, the outline of the fixture's ink
    box: BBox


@dataclass(frozen=True)
class _Kept:
    window: tuple[slice, slice]
    hole: Mask  # within the window
    own: Mask  # the fixture's ink, within the window
    rim_wall: float  # share of the rim on the first trace's walls


@dataclass(frozen=True)
class Fixtures:
    fixtures: list[Fixture]
    carve: Mask  # ink to leave out of the wall trace
    self_closed: Mask  # ink of fixtures closed without a wall: left out of the door scan
    kept: tuple[_Kept, ...] = ()


def find_fixtures(
    ink: Mask, walls: Mask, lines: Mask, min_run_px: int, text_boxes: Sequence[BBox] = ()
) -> Fixtures:
    """`walls`: the first trace's walls as a mask; `lines`: its thin-line walls;
    `text_boxes`: words that read as text."""
    text = box_mask(ink.shape, text_boxes)
    bands = band_mask(ink, min_run_px, text)
    closed = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_CLOSE, _EIGHT).astype(bool)
    thick = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_OPEN, _EIGHT).astype(bool)
    holes = ndimage.binary_fill_holes(closed) & ~closed
    _, lab = cv2.connectedComponents(holes.astype(np.uint8), connectivity=4)
    areas = np.bincount(lab.ravel())
    max_side = SIDE_SHARE * max(ink.shape)
    reach = np.ones((2 * REACH_PX + 1,) * 2, np.uint8)
    kept = []
    for index, found in enumerate(ndimage.find_objects(lab), start=1):
        if found is None:
            continue
        h, w = found[0].stop - found[0].start, found[1].stop - found[1].start
        area = int(areas[index])
        if max(w, h) > max_side or area > max_side**2:
            continue
        if min(w, h) < MIN_SIDE_PX or area < MIN_AREA_PX:
            continue
        if min(w, h) <= STRIP_PX and max(w, h) >= STRIP_ASPECT * min(w, h):
            continue
        pad = REACH_PX + 1
        win = (
            slice(max(0, found[0].start - pad), found[0].stop + pad),
            slice(max(0, found[1].start - pad), found[1].stop + pad),
        )
        hole = lab[win] == index
        rim = cv2.dilate(hole.astype(np.uint8), _EIGHT).astype(bool) & ~hole & ink[win]
        rim_px = int(rim.sum()) or 1
        if (
            int((rim & thick[win]).sum()) > RIM_THICK * rim_px
            or int((rim & bands[win]).sum()) < RIM_BAND * rim_px
            or float(text[win][hole].mean()) > TEXT_SHARE
            or _neighbours(lab, closed, found, index, area, areas) > MAX_NEIGHBOURS
            or _fill(hole) < MIN_FILL
        ):
            continue
        near = cv2.dilate(hole.astype(np.uint8), reach).astype(bool)
        own = (hole & ink[win]) | (near & ink[win] & ~thick[win] & ~lines[win])
        kept.append(_Kept(win, hole, own, int((rim & walls[win]).sum()) / rim_px))
    return _gathered(kept, ink.shape)


def without_swings(found: Fixtures, doors: Sequence[Door]) -> Fixtures:
    """The fixtures less the holes that are a found door's swing: its quarter disc."""
    swing = np.zeros(found.carve.shape, np.uint8)
    for d in doors:
        start, sweep = arc_angles(d)
        r = round(d.radius_px) + SWING_MARGIN_PX
        hinge = (round(d.a[0]), round(d.a[1]))
        cv2.ellipse(swing, hinge, (r, r), 0, start, start + sweep, 1, -1)
    kept = [k for k in found.kept if float(swing[k.window][k.hole].mean()) < SWING_SHARE]
    return found if len(kept) == len(found.kept) else _gathered(kept, found.carve.shape)


def _neighbours(
    lab: np.ndarray,
    closed: Mask,
    found: tuple[slice, slice],
    index: int,
    area: int,
    areas: np.ndarray,
) -> int:
    """The regions within `NEIGHBOUR_PX` of the hole at least `NEIGHBOUR_TIMES` its size:
    the other holes of the closed ink, and the page's outside as one."""
    pad = NEIGHBOUR_PX + 1
    win = (
        slice(max(0, found[0].start - pad), found[0].stop + pad),
        slice(max(0, found[1].start - pad), found[1].stop + pad),
    )
    sub = lab[win]
    hole = sub == index
    size = 2 * NEIGHBOUR_PX + 1
    near = cv2.dilate(hole.astype(np.uint8), np.ones((size, size), np.uint8)).astype(bool)
    labels = np.unique(sub[near & ~hole & ~closed[win]])
    return sum(1 for v in labels if v == 0 or areas[v] >= NEIGHBOUR_TIMES * area)


def _fill(hole: Mask) -> float:
    """How much of its box the hole fills once strokes inside it are closed over."""
    kernel = np.ones((FILL_CLOSE_PX,) * 2, np.uint8)
    padded = np.pad(hole, FILL_CLOSE_PX).astype(np.uint8)
    filled = cv2.morphologyEx(padded, cv2.MORPH_CLOSE, kernel).astype(bool)
    ys, xs = np.nonzero(filled)
    return int(filled.sum()) / int((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1))


def _gathered(kept: Sequence[_Kept], shape: tuple[int, ...]) -> Fixtures:
    """One fixture per patch of carved ink: nested outlines and a table's chairs that
    touch it are one outline."""
    carve = np.zeros(shape[:2], dtype=bool)
    self_closed = np.zeros(shape[:2], dtype=bool)
    for k in kept:
        carve[k.window] |= k.own
        if k.rim_wall <= SELF_CLOSED:
            self_closed[k.window] |= k.own
    reach = np.ones((2 * REACH_PX + 1,) * 2, np.uint8)
    patches = cv2.morphologyEx(carve.astype(np.uint8), cv2.MORPH_CLOSE, reach)
    contours, _ = cv2.findContours(patches, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    fixtures = []
    for c in contours:
        if len(c) < 3:
            continue
        points = cv2.approxPolyDP(c, POLYGON_EPSILON, True).reshape(-1, 2)
        polygon = [(float(x), float(y)) for x, y in points]
        xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
        fixtures.append(Fixture(polygon, (min(xs), min(ys), max(xs), max(ys))))
    return Fixtures(fixtures, carve, self_closed, tuple(kept))
