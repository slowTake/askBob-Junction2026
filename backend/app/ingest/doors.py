"""Doors read from a raster page's symbol layer: a leaf and its quarter arc (D-055).

A door is drawn as its leaf, a straight line from the hinge across the wall, and the arc
the leaf's free end sweeps back to the wall. Both are thin, and often coloured, so they
are read on the symbol layer (`ColourLayers.symbols`) with the thick wall ink taken off.
For every hinge near a traced wall, radius and quadrant, a door is:
- an arc: thin ink in `ARC_HITS` of the quarter's `BINS` angular sectors at the radius,
  and little ink on the rings just inside and outside it (a line, not a hatched patch);
- an empty swing: the quarter disc inside the arc holds little ink and no wall;
- a leaf: ink along most of the line from the hinge to the arc's end across the wall;
- on a wall at both ends: the hinge and the arc's other end, where the door closes.
Every such candidate is then moved onto its wall's centre line and kept only if (D-057):
- its gap lies on a traced wall;
- its leaf is not a wall that runs on past the leaf's end (a wall corner);
- its arc does not run on past both of its ends (a circle or a rounded corner).
Overlapping doors keep the one whose arc is longest and fits its radius best, and of
equal ones the one whose hinge is nearest the wall.

Pure: masks in, dataclasses out.
"""

import math
from dataclasses import dataclass

import cv2
import numpy as np

from app.domain.geometry import Point
from app.ingest.rooms import Mask

BINS = 9  # 10-degree sectors of the quarter
BAND_PX = 1.5  # the arc lies this close to its radius: drawn by hand or scanned
ARC_HITS = 0.9  # share of the sectors with arc ink: all but one
RING_STEP_PX = 3.5  # the rings beside the arc, inside and outside
INNER_HITS = 0.34  # at most this share of their sectors with ink (the leaf and wall: 2/9)
OUTER_HITS = 0.45
SWING_MARGIN_PX = 3  # the swing read this far in from the leaf, wall and arc
SWING_INK = 0.2  # at most this share of the swing is ink (text, a dimension line)
SWING_WALL = 0.08  # and of traced wall
LEAF_SHARE = 0.7  # at least this share of the leaf line is ink
WALL_NEAR_PX = 2  # the hinge and the free end lie this close to a traced wall
TIE_PER_PX = 0.1  # of equal arcs, the hinge nearer the wall wins (less than a sector)
OVERLAP = 0.1  # doors whose boxes overlap more than this (of the smaller) are one
CARVE_PX = 1  # the leaf and arc are carved this much wider than drawn
WORK_SIDE_PX = 700  # bigger pages are read at this size: 3 s on a 3,000 px page
CENTRE_PX = 6  # a gap moves at most this far across its wall, onto the wall's centre (D-057)
GAP_ON_WALL = 0.9  # at least this share of the gap lies within 1 px of a traced wall
LEAF_ON_WALL = 0.5  # a leaf more than this share on a traced wall (from SWING_MARGIN_PX out)
RUNS_ON = 0.6  # whose wall goes on over this share of PAST_LEAF_PX past its end is a wall
PAST_LEAF_PX = (3, 8)
BEYOND_HITS = 1  # an arc inked in more of the 3 sectors past each end than this is a circle
BEYOND_BAND_PX = 2  # read 0.5 px wider than BAND_PX: a circle read 1 px off its centre drifts


@dataclass(frozen=True)
class Door:
    a: Point  # the hinge, on the wall
    b: Point  # where the leaf closes, on the wall: the gap is a..b
    toward: Point  # a point in the swing: the side the door opens into
    leaf: Point  # the leaf's free end, drawn open
    radius_px: float


def find_doors(
    symbols: Mask, ink: Mask, walls: Mask, min_radius_px: int, max_radius_px: int
) -> list[Door]:
    """Doors with a leaf `min_radius_px` to `max_radius_px` long. `walls` is the traced
    walls as a mask."""
    scale = min(1.0, WORK_SIDE_PX / max(symbols.shape))
    if scale < 1.0:
        symbols, ink, walls = (_shrink(m, scale) for m in (symbols, ink, walls))
    thick = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    arc = (symbols & ~thick.astype(bool)).astype(np.uint8)
    lines = symbols.astype(np.uint8)
    away = cv2.distanceTransform((~walls).astype(np.uint8), cv2.DIST_L2, 3)
    radii = _radii(max(3, round(min_radius_px * scale)), round(max_radius_px * scale))
    on_wall = cv2.dilate(walls.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    found = []
    for score, door in _candidates(arc, lines, walls, away, radii):
        centred = _centred(door, walls)
        if _accepted(door, centred, arc, on_wall, away):
            found.append((score, centred))
    kept = _suppressed(found)
    return [_scaled(d, 1 / scale) for d in kept] if scale < 1.0 else kept


def _candidates(
    arc: np.ndarray, lines: np.ndarray, walls: Mask, away: np.ndarray, radii: list[int]
) -> list[tuple[float, Door]]:
    """Every reading of a leaf and arc at every radius and quadrant, with its score."""
    found = []
    for r in radii:
        for sx in (1, -1):
            for sy in (1, -1):
                found += _quadrant(arc, lines, walls, away, r, sx, sy)
    return found


def _accepted(door: Door, centred: Door, arc: np.ndarray, on_wall: Mask, away: np.ndarray) -> bool:
    """A candidate is a door only if its centred gap lies on a wall, its leaf is not a
    wall that runs on past the leaf's end, and its arc stops at its ends. The leaf is
    read where it was found; the arc's ends round both hinges, as found and centred: a
    circle read from a hinge up to WALL_NEAR_PX off its centre drifts off the ring past
    its ends, and centring puts that hinge back on the centre. The rules run before the
    candidates compete, so a wrong reading of an arc frees the right one."""
    if not _gap_on_wall(centred, on_wall):
        return False
    if _leaf_runs_on(door, away) or _arc_runs_on(door, arc):
        return False
    return centred == door or not _arc_runs_on(centred, arc)


def _gap_on_wall(d: Door, on_wall: Mask) -> bool:
    """The gap lies on a traced wall, or it is a break in one: the wall goes on in line
    past both of its ends and stops at them, leaving the gap's inside (from 3 px in) open
    (a drawing that leaves the doorway open)."""
    if _share_on(on_wall, d.a, d.b) >= GAP_ON_WALL:
        return True
    length = math.dist(d.a, d.b) or 1.0
    gx, gy = (d.b[0] - d.a[0]) / length, (d.b[1] - d.a[1]) / length
    lo, hi = PAST_LEAF_PX

    def at(p: Point, k: float) -> Point:
        return (p[0] + k * gx, p[1] + k * gy)

    past = min(
        _share_on(on_wall, at(d.a, -lo), at(d.a, -hi)),
        _share_on(on_wall, at(d.b, lo), at(d.b, hi)),
    )
    inside = _share_on(on_wall, at(d.a, lo), at(d.b, -lo)) if length > 2 * lo else 0.0
    return past >= RUNS_ON and inside <= 1 - GAP_ON_WALL


def _leaf_runs_on(d: Door, away: np.ndarray) -> bool:
    """The leaf lies on a traced wall that goes on past the leaf's end: a wall corner
    read as a leaf. A thin leaf traced as a short wall stops where the leaf does."""
    ux, uy = _leaf_unit(d)
    m, r, near = SWING_MARGIN_PX, d.radius_px, away <= WALL_NEAR_PX

    def at(k: float) -> Point:
        return (d.a[0] + k * ux, d.a[1] + k * uy)

    lo, hi = PAST_LEAF_PX
    leaf = _share_on(near, at(m), d.leaf)
    return leaf > LEAF_ON_WALL and _share_on(near, at(r + lo), at(r + hi)) >= RUNS_ON


def _arc_runs_on(d: Door, arc: np.ndarray) -> bool:
    """The ring goes on past both ends of the quarter arc: a circle or a rounded corner.
    Past the leaf's end from 5 degrees; past the free end from 15 degrees, beyond the
    wall the gap lies on. One end alone is not enough: a band's halo or the next door's
    arc can run on past one end of a real door."""
    leaf = math.degrees(math.atan2(d.leaf[1] - d.a[1], d.leaf[0] - d.a[0]))
    free = math.degrees(math.atan2(d.b[1] - d.a[1], d.b[0] - d.a[0]))
    sense = 1 if ((free - leaf + 180) % 360) - 180 > 0 else -1  # from the leaf to b
    return (
        _ring_hits(d, arc, leaf, -sense, 5) > BEYOND_HITS
        and _ring_hits(d, arc, free, sense, 15) > BEYOND_HITS
    )


def _ring_hits(d: Door, arc: np.ndarray, start: float, sense: int, first: float) -> int:
    """Of the 3 ten-degree sectors of the door's ring from `first` degrees past the
    angle `start` (turning by `sense`), how many hold arc ink. Read in a window round
    the hinge; a window cut by the page's edge reads none."""
    r, (ax, ay) = d.radius_px, d.a
    size, x0, y0 = int(r + 4), round(ax), round(ay)
    window = arc[max(0, y0 - size) : y0 + size + 1, max(0, x0 - size) : x0 + size + 1]
    if window.shape != (2 * size + 1, 2 * size + 1):
        return 0
    ys, xs = np.mgrid[-size : size + 1, -size : size + 1]
    dx, dy = xs + (x0 - ax), ys + (y0 - ay)
    turned = ((np.degrees(np.arctan2(dy, dx)) - start) * sense) % 360
    ring = np.abs(np.hypot(dx, dy) - r) <= BEYOND_BAND_PX
    return sum(
        bool(window[ring & (turned >= first + 10 * k) & (turned < first + 10 * (k + 1))].any())
        for k in range(3)
    )


def _share_on(layer: Mask, p: Point, q: Point) -> float:
    """Share of the pixels of the segment p..q (clipped to the page) set in `layer`."""
    n = int(math.dist(p, q)) + 1
    height, width = layer.shape
    xs = np.round(np.linspace(p[0], q[0], n)).astype(int).clip(0, width - 1)
    ys = np.round(np.linspace(p[1], q[1], n)).astype(int).clip(0, height - 1)
    return float(layer[ys, xs].mean())


def _centred(d: Door, walls: Mask) -> Door:
    """The door moved along its leaf so its gap lies on the centre of the wall's run
    through the gap's middle (the nearest run within `CENTRE_PX`, if the middle is off
    the wall). A door drawn over a band is read from the band's edge; CAD and the truth
    put the gap on the wall's centre line."""
    ux, uy = _leaf_unit(d)
    mx, my = (d.a[0] + d.b[0]) / 2, (d.a[1] + d.b[1]) / 2
    height, width = walls.shape
    on = {}
    for o in range(-CENTRE_PX, CENTRE_PX + 1):
        x, y = round(mx + o * ux), round(my + o * uy)
        on[o] = 0 <= x < width and 0 <= y < height and bool(walls[y, x])
    hits = [o for o, wall in on.items() if wall]
    if not hits:
        return d
    lo = hi = 0 if on[0] else min(hits, key=abs)
    while on.get(lo - 1, False):
        lo -= 1
    while on.get(hi + 1, False):
        hi += 1
    shift = (lo + hi) / 2
    if shift == 0:
        return d

    def moved(p: Point) -> Point:
        return (p[0] + shift * ux, p[1] + shift * uy)

    return Door(moved(d.a), moved(d.b), moved(d.toward), moved(d.leaf), d.radius_px)


def _leaf_unit(d: Door) -> tuple[float, float]:
    """The unit vector from the hinge along the leaf: across the wall."""
    return (d.leaf[0] - d.a[0]) / d.radius_px, (d.leaf[1] - d.a[1]) / d.radius_px


def _suppressed(found: list[tuple[float, Door]]) -> list[Door]:
    """Non-maximum suppression: the best scored of overlapping candidates is the door."""
    kept: list[Door] = []
    for _, door in sorted(found, key=lambda c: -c[0]):
        if all(_overlap(door, k) <= OVERLAP for k in kept):
            kept.append(door)
    return kept


def door_carve(doors: list[Door], symbols: Mask, ink: Mask) -> Mask:
    """The doors' leaves and arcs as drawn, to be left out of the walls. Thick ink (a
    wall band the arc crosses) and the gap's line (the wall through the door) are never
    carved."""
    drawn = np.zeros(symbols.shape, np.uint8)
    for d in doors:
        r = round(d.radius_px)
        width = 2 * CARVE_PX + 1
        cv2.line(drawn, _px(d.a), _px(d.leaf), 1, width)
        start, sweep = _arc_angles(d)
        cv2.ellipse(drawn, _px(d.a), (r, r), 0, start, start + sweep, 1, width)
    thick = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    carve = drawn.astype(bool) & symbols & ~thick.astype(bool)
    rows, cols = np.mgrid[0 : symbols.shape[0], 0 : symbols.shape[1]]
    for d in doors:  # keep the wall: pixels within CARVE_PX of the gap's line stay
        (ax, ay), (bx, by) = d.a, d.b
        length = math.dist(d.a, d.b) or 1.0
        across = np.abs((bx - ax) * (rows - ay) - (by - ay) * (cols - ax)) / length
        carve &= ~(across <= CARVE_PX)
    return carve


def _quadrant(
    arc: np.ndarray, lines: np.ndarray, walls: Mask, away: np.ndarray, r: int, sx: int, sy: int
) -> list[tuple[float, Door]]:
    near = away <= WALL_NEAR_PX
    size = r + SWING_MARGIN_PX + 3
    ys, xs = np.mgrid[-size : size + 1, -size : size + 1]
    ax, ay = xs * sx, ys * sy  # into the quadrant
    dist = np.hypot(xs, ys)
    angle = np.degrees(np.arctan2(ay, ax))
    quarter = (ax >= 0) & (ay >= 0)

    def hits(radius: float, layer: np.ndarray, band: float = BAND_PX) -> np.ndarray:
        count = np.zeros(layer.shape, np.float32)
        for b in range(BINS):
            lo, hi = 90 * b / BINS, 90 * (b + 1) / BINS
            sector = quarter & (np.abs(dist - radius) <= band) & (angle >= lo) & (angle <= hi)
            count += cv2.dilate(layer, sector.astype(np.uint8), borderValue=0) > 0
        return count / BINS

    swing = (ax >= SWING_MARGIN_PX) & (ay >= SWING_MARGIN_PX) & (dist <= r - SWING_MARGIN_PX)
    cover = hits(r, arc)
    ok = (cover >= ARC_HITS) & near
    if not ok.any():
        return []
    ok &= hits(r + RING_STEP_PX, lines) <= OUTER_HITS
    if r - RING_STEP_PX > SWING_MARGIN_PX:
        ok &= hits(r - RING_STEP_PX, lines) <= INNER_HITS
    if swing.sum() >= 4:
        ok &= _share(lines, swing) <= SWING_INK
        ok &= _share(walls.astype(np.uint8), swing) <= SWING_WALL
    # The arc's length scores the door, times how closely its ink keeps to the radius:
    # 1 - the ink's mean distance from the radius, as a share of the band.
    band = (quarter & (np.abs(dist - r) <= BAND_PX)).astype(np.float32)
    off = band * np.abs(dist - r).astype(np.float32)
    layer = arc.astype(np.float32)
    inked = cv2.filter2D(layer, -1, band, borderType=cv2.BORDER_CONSTANT)
    spread = cv2.filter2D(layer, -1, off, borderType=cv2.BORDER_CONSTANT) / np.maximum(inked, 1)
    fit = cover * (1 - spread / BAND_PX)
    found = []
    height, width = arc.shape
    # Along the wall to the free end t, across it along the leaf n: either axis can be the wall.
    for t, n in (((sx, 0), (0, sy)), ((0, sy), (sx, 0))):
        leaf = np.zeros((2 * size + 1,) * 2, np.uint8)
        cv2.line(leaf, (size, size), (size + n[0] * r, size + n[1] * r), 1, 1)
        here = ok & (_share(lines, leaf.astype(bool)) >= LEAF_SHARE)
        for y, x in zip(*np.nonzero(here), strict=True):
            fx, fy = int(x) + t[0] * r, int(y) + t[1] * r
            if not (0 <= fx < width and 0 <= fy < height and near[fy, fx]):
                continue
            hinge = (float(x), float(y))
            door = Door(
                a=hinge,
                b=(float(fx), float(fy)),
                toward=(x + (t[0] + n[0]) * r / 2, y + (t[1] + n[1]) * r / 2),
                leaf=(float(x + n[0] * r), float(y + n[1] * r)),
                radius_px=float(r),
            )
            found.append((float(fit[y, x]) * r - TIE_PER_PX * float(away[y, x]), door))
    return found


def _share(layer: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Share of `kernel`'s pixels (centred on each pixel) that are set in `layer`."""
    k = kernel.astype(np.float32) / float(kernel.sum())
    return cv2.filter2D(layer.astype(np.float32), -1, k, borderType=cv2.BORDER_CONSTANT)


def _radii(lo: int, hi: int) -> list[int]:
    """Every radius up to 20 px, then steps of 1/20 of the radius: within the arc band."""
    radii, r = [], lo
    while r <= hi:
        radii.append(r)
        r += max(1, r // 20)
    return radii


def _box(d: Door) -> tuple[float, float, float, float]:
    xs = (d.a[0], d.b[0], d.leaf[0])
    ys = (d.a[1], d.b[1], d.leaf[1])
    return min(xs), min(ys), max(xs), max(ys)


def _overlap(d: Door, e: Door) -> float:
    (a0, a1, a2, a3), (b0, b1, b2, b3) = _box(d), _box(e)
    inter = max(0.0, min(a2, b2) - max(a0, b0)) * max(0.0, min(a3, b3) - max(a1, b1))
    smaller = min((a2 - a0) * (a3 - a1), (b2 - b0) * (b3 - b1))
    return inter / smaller if smaller > 0 else 0.0


def _arc_angles(d: Door) -> tuple[float, float]:
    """The arc from the leaf's end to the free end: its start angle and its 90-degree
    sweep, in OpenCV's degrees (y down)."""
    start = math.degrees(math.atan2(d.leaf[1] - d.a[1], d.leaf[0] - d.a[0]))
    end = math.degrees(math.atan2(d.b[1] - d.a[1], d.b[0] - d.a[0]))
    if (end - start) % 360 > 180:
        start, end = end, start
    return start, (end - start) % 360


def _shrink(mask: Mask, scale: float) -> Mask:
    size = (round(mask.shape[1] * scale), round(mask.shape[0] * scale))
    return cv2.resize(mask.astype(np.uint8) * 255, size, interpolation=cv2.INTER_AREA) > 0


def _scaled(d: Door, k: float) -> Door:
    def p(v: Point) -> Point:
        return (v[0] * k, v[1] * k)

    return Door(p(d.a), p(d.b), p(d.toward), p(d.leaf), d.radius_px * k)


def _px(p: Point) -> tuple[int, int]:
    return round(p[0]), round(p[1])
