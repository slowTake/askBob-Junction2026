"""Walls traced from a raster page's ink as polygons (D-053).

Two kinds of wall drawing, read separately:
- **bands**: walls drawn solid, hatched or as a close double line. The ink is closed over
  hatching and double-line gaps, and what stays at least `BAND_MIN_PX` thick is a band.
  A band network (walls meeting at corners and junctions) is cut along its skeleton
  into simple pieces, one per branch, so no polygon ever covers the room it encloses;
  an L-shaped or slanted band without a junction stays one polygon.
- **lines**: walls drawn as one thin line. Straight horizontal or vertical runs at least
  `min_run_px` long, which leaves out dashes, letters and hatching; a scanned line may
  step by a row along the way. Lines along a printed dimension are dimension lines.

Text the OCR read is not a wall: a band that lies mostly inside word boxes is dropped,
and word boxes are cut out of the thin lines. Pure: arrays in, polygons out.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np
from scipy import ndimage
from skimage.morphology import skeletonize

from app.domain.geometry import BBox, Point
from app.ingest.line_trace import BAND_CLOSE_PX
from app.ingest.rooms import Mask

BAND_MIN_PX = 3  # thinner than this after closing is a line, not a band
TEXT_SHARE = 0.5  # a band mostly inside word boxes is lettering
MIN_PIECE_PX = 9  # a band piece smaller than 3 x 3 px is a fringe of its neighbours
DIMENSION_REACH = 1.5  # a dimension line lies within 1.5 label heights of its label
COLLINEAR_PX = 1.5  # a run continues a dimension line when its centre line is this close
POLYGON_EPSILON = 1.0  # outline simplification, px
# A band's own strokes are straight: solid ink, edges, double lines, hatching. Handwriting
# and fixture symbols closed into a band are mostly curves. Share of a band piece's ink on
# straight runs of `STROKE_RUN_PX` in one of eight directions (D-053, on colorful-34).
STROKE_RUN_PX = 9
STRAIGHT_SHARE = 0.6

_EIGHT = np.ones((3, 3), np.uint8)


@dataclass(frozen=True)
class TracedWall:
    polygon: list[Point]  # page px
    thickness_px: float  # measured from the ink
    drawn: Literal["band", "line"]


def trace_walls(
    ink: Mask,
    min_run_px: int,
    text_boxes: Sequence[BBox] = (),
    dimension_boxes: Sequence[BBox] = (),
    carve: Mask | None = None,
) -> list[TracedWall]:
    """The page's walls: bands first, then the thin lines that are not part of a band.

    `text_boxes` are words that read as text; `dimension_boxes` the printed dimensions.
    `carve` is ink drawn as something else (window frames, door leaves and arcs, D-055):
    it is taken off before tracing, so it is neither a wall nor closed into one.
    """
    if carve is not None:
        ink = ink & ~carve
    text = _box_mask(ink.shape, text_boxes)
    bands = _band_mask(ink, min_run_px, text)
    straight = _straight_strokes(ink)
    walls = [
        wall
        for piece in _band_pieces(bands)
        if int((straight[piece.window] & piece.mask).sum())
        >= STRAIGHT_SHARE * int((ink[piece.window] & piece.mask).sum())
        for wall in _band_walls(piece)
    ]
    thin = ink & ~cv2.dilate(bands.astype(np.uint8), _EIGHT).astype(bool) & ~text
    runs = _thin_runs(thin, min_run_px)
    dimensions = _dimension_lines(runs, dimension_boxes, min_run_px)
    walls += [_line_wall(r) for i, r in enumerate(runs) if i not in dimensions]
    return walls


def _box_mask(shape: tuple[int, ...], boxes: Sequence[BBox]) -> Mask:
    mask = np.zeros(shape[:2], dtype=bool)
    for x0, y0, x1, y1 in boxes:
        mask[max(0, int(y0)) : int(np.ceil(y1)) + 1, max(0, int(x0)) : int(np.ceil(x1)) + 1] = True
    return mask


def _band_mask(ink: Mask, min_run_px: int, text: Mask) -> Mask:
    """Ink at least `BAND_MIN_PX` thick once hatching and double lines are closed, in
    components that span a wall run and are not mostly lettering."""
    closed = cv2.morphologyEx(
        ink.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((BAND_CLOSE_PX,) * 2, np.uint8)
    )
    thick = cv2.morphologyEx(closed, cv2.MORPH_OPEN, np.ones((BAND_MIN_PX,) * 2, np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(thick, connectivity=8)
    span = np.maximum(stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT])
    in_text = np.bincount(np.asarray(labels[text], dtype=np.int64), minlength=count)
    keep = (span >= min_run_px) & (in_text <= TEXT_SHARE * stats[:, cv2.CC_STAT_AREA])
    keep[0] = False  # background
    return np.asarray(keep[labels], dtype=np.bool_)


@dataclass(frozen=True)
class _Piece:
    window: tuple[slice, slice]  # rows, columns of the page
    mask: Mask  # the piece within its window
    thickness: float

    @property
    def origin(self) -> tuple[int, int]:
        return int(self.window[1].start), int(self.window[0].start)


def _band_pieces(bands: Mask) -> list[_Piece]:
    """Every band pixel goes to its nearest skeleton branch; junctions split branches."""
    if not bands.any():
        return []
    skeleton = skeletonize(bands)
    neighbours = ndimage.convolve(skeleton.astype(np.uint8), _EIGHT, mode="constant") - 1
    junctions = skeleton & (neighbours >= 3)
    branches = skeleton & ~cv2.dilate(junctions.astype(np.uint8), _EIGHT).astype(bool)
    count, branch = cv2.connectedComponents(branches.astype(np.uint8), connectivity=8)
    # A blob whose skeleton is all junction keeps its skeleton as its one branch.
    _, blob = cv2.connectedComponents(bands.astype(np.uint8), connectivity=8)
    bare = skeleton & ~np.isin(blob, np.unique(blob[branch > 0]))
    branch = np.where(bare, blob + count, branch)
    # The nearest branch pixel to every pixel: a label per branch pixel, mapped to its branch.
    _, nearest = cv2.distanceTransformWithLabels(
        (branch == 0).astype(np.uint8), cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_PIXEL
    )
    ys, xs = np.nonzero(branch)
    to_branch = np.zeros(int(nearest.max()) + 1, np.int32)
    to_branch[nearest[ys, xs]] = branch[ys, xs]
    owner = np.where(bands, to_branch[nearest], 0)
    depth = cv2.distanceTransform(bands.astype(np.uint8), cv2.DIST_L2, 3)
    pieces = []
    for index, window in enumerate(ndimage.find_objects(owner), start=1):
        if window is None:
            continue
        piece = owner[window] == index
        spine = depth[window][skeleton[window] & piece]
        thickness = 2 * float(np.median(spine)) if spine.size else 0.0
        pieces.append(_Piece(window, piece, thickness or 2 * float(depth[window][piece].max())))
    return pieces


def _straight_strokes(ink: Mask) -> Mask:
    """Ink on a straight run of `STROKE_RUN_PX` along 0, 30, 45, ... 150 degrees."""
    size, middle = STROKE_RUN_PX, STROKE_RUN_PX // 2
    lines = ink.astype(np.uint8)
    straight = np.zeros(ink.shape, dtype=bool)
    for degrees in range(0, 180, 15):
        if degrees % 45 and degrees % 30:
            continue  # 0, 30, 45, 60, 90, 120, 135, 150
        kernel = np.zeros((size, size), np.uint8)
        dx, dy = middle * np.cos(np.radians(degrees)), middle * np.sin(np.radians(degrees))
        start, end = (
            (round(middle - dx), round(middle - dy)),
            (round(middle + dx), round(middle + dy)),
        )
        cv2.line(kernel, start, end, 1, 1)
        straight |= cv2.morphologyEx(lines, cv2.MORPH_OPEN, kernel).astype(bool)
    return straight


def _band_walls(piece: _Piece) -> list[TracedWall]:
    return [
        TracedWall(polygon, round(piece.thickness, 1), "band")
        for part in _without_holes(piece.mask)
        if int(part.sum()) >= MIN_PIECE_PX and len(polygon := _outline(part, piece.origin)) >= 3
    ]


def _without_holes(piece: Mask) -> list[Mask]:
    """A piece as parts without holes: a ring is cut in two at its hole's centre."""
    contours, hierarchy = cv2.findContours(
        piece.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE
    )
    holes = (
        [c for c, h in zip(contours, hierarchy[0], strict=True) if h[3] >= 0] if contours else []
    )
    if not holes:
        return _components(piece)
    x, _, w, _ = cv2.boundingRect(holes[0])
    columns = np.arange(piece.shape[1]) < x + w // 2
    return _without_holes(piece & columns) + _without_holes(piece & ~columns)


def _components(mask: Mask) -> list[Mask]:
    count, labels = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
    return [labels == i for i in range(1, count)]


def _outline(part: Mask, origin: tuple[int, int]) -> list[Point]:
    contours, _ = cv2.findContours(part.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    outline = max(contours, key=cv2.contourArea)
    points = cv2.approxPolyDP(outline, POLYGON_EPSILON, True).reshape(-1, 2)
    return [(float(x + origin[0]), float(y + origin[1])) for x, y in points]


@dataclass(frozen=True)
class _Run:
    box: tuple[int, int, int, int]  # first and last column, first and last row
    xy: np.ndarray  # its pixels, (n, 2) columns and rows
    horizontal: bool

    @property
    def length(self) -> int:
        x0, y0, x1, y1 = self.box
        return x1 - x0 + 1 if self.horizontal else y1 - y0 + 1

    @property
    def centre(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self.box
        return (x0 + x1) / 2, (y0 + y1) / 2


def _thin_runs(thin: Mask, min_run_px: int) -> list[_Run]:
    """Straight horizontal and vertical runs of `min_run_px` or longer. The line is
    widened by a pixel across before the run test, so a scanned line that steps by a
    row is still one run; only its own pixels are kept."""
    lines = thin.astype(np.uint8)
    runs = []
    for horizontal in (True, False):
        across = np.ones((3, 1) if horizontal else (1, 3), np.uint8)
        size = min_run_px | 1  # odd: an even kernel shifts the run by a pixel
        along = np.ones((1, size) if horizontal else (size, 1), np.uint8)
        opened = cv2.morphologyEx(cv2.dilate(lines, across), cv2.MORPH_OPEN, along)
        straight = (opened > 0).astype(np.uint8) & lines
        _, labels, stats, _ = cv2.connectedComponentsWithStats(straight, connectivity=8)
        for index, window in enumerate(ndimage.find_objects(labels), start=1):
            x, y, w, h = (int(v) for v in stats[index][:4])
            rows, cols = np.nonzero(labels[window] == index)
            xy = np.stack([cols + x, rows + y], axis=1)
            run = _Run((x, y, x + w - 1, y + h - 1), xy, horizontal)
            if run.length >= min_run_px:
                runs.append(run)
    return runs


def _dimension_lines(runs: list[_Run], labels: Sequence[BBox], min_run_px: int) -> set[int]:
    """Runs that carry a printed dimension: parallel to its label, within reach of it and
    passing its centre, and the runs that continue one in line (past a tick)."""
    found = set()
    for i, run in enumerate(runs):
        start, end = _extent(run)
        for x0, y0, x1, y1 in labels:
            if run.horizontal:
                (lo, hi), across, size = (x0, x1), (y0 + y1) / 2, y1 - y0
            else:
                (lo, hi), across, size = (y0, y1), (x0 + x1) / 2, x1 - x0
            # The label sits along the run, or the run ends at it: its box cut the line.
            alongside = start - min_run_px <= hi and lo <= end + min_run_px
            if alongside and abs(_offset(run) - across) <= DIMENSION_REACH * size:
                found.add(i)
    grown = True
    while grown:
        grown = False
        for i, run in enumerate(runs):
            if i not in found and any(_continues(runs[j], run, min_run_px) for j in found):
                found.add(i)
                grown = True
    return found


def _extent(run: _Run) -> tuple[int, int]:
    x0, y0, x1, y1 = run.box
    return (x0, x1) if run.horizontal else (y0, y1)


def _offset(run: _Run) -> float:
    return run.centre[1] if run.horizontal else run.centre[0]


def _continues(a: _Run, b: _Run, gap_px: int) -> bool:
    if a.horizontal != b.horizontal or abs(_offset(a) - _offset(b)) > COLLINEAR_PX:
        return False
    (a0, a1), (b0, b1) = _extent(a), _extent(b)
    return max(a0, b0) - min(a1, b1) <= gap_px


def _line_wall(run: _Run) -> TracedWall:
    """A band along the line fitted through the run's pixels, as thick as the run's pixels
    per unit length, out to the pixels' outer edges (pixel x spans x - 0.5 .. x + 0.5).
    A scanned line that steps by a row stays 1 px thick instead of becoming its box."""
    points = run.xy.astype(np.float32)
    vx, vy, cx, cy = (float(v) for v in cv2.fitLine(points, cv2.DIST_L2, 0, 0.01, 0.01).ravel())
    if (vx if run.horizontal else vy) < 0:
        vx, vy = -vx, -vy
    along = (points[:, 0] - cx) * vx + (points[:, 1] - cy) * vy
    start, end = float(along.min()) - 0.5, float(along.max()) + 0.5
    thickness = len(points) / run.length
    nx, ny = -vy * thickness / 2, vx * thickness / 2
    ends = [(cx + vx * t, cy + vy * t) for t in (start, end)]
    polygon = [
        (round(x + sx * nx, 3), round(y + sx * ny, 3))
        for (x, y), sx in ((ends[0], -1), (ends[1], -1), (ends[1], 1), (ends[0], 1))
    ]
    return TracedWall(polygon, round(thickness, 1), "line")


COVERED_SHARE = 0.5  # a model wall this much over traced walls is one the ink already has
MODEL_TOLERANCE_PX = 2  # the model's outline sits a pixel or two off the ink


def model_walls_beyond(
    traced: Sequence[TracedWall], model: Sequence[list[Point]], shape: tuple[int, ...]
) -> list[list[Point]]:
    """The floor-plan model's walls that add to the traced ones (D-053): where the model
    and the ink both have a wall, the ink's outline is kept."""
    drawn = np.zeros(shape[:2], np.uint8)
    for wall in traced:
        cv2.fillPoly(drawn, [np.round(np.array(wall.polygon)).astype(np.int32)], 1)
    size = 2 * MODEL_TOLERANCE_PX + 1
    near = cv2.dilate(drawn, np.ones((size, size), np.uint8)).astype(bool)
    kept = []
    for polygon in model:
        own = np.zeros(shape[:2], np.uint8)
        cv2.fillPoly(own, [np.round(np.array(polygon)).astype(np.int32)], 1)
        area = int(own.sum())
        if area == 0 or int((own.astype(bool) & near).sum()) < COVERED_SHARE * area:
            kept.append(polygon)
    return kept
