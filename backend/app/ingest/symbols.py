"""Doors and windows read from a raster page's symbol layer (D-055).

A window is drawn as a glazing strip: a thin rectangle frame, often split into panes by
mullions, lying along a wall on the outside of the building. On the symbol layer
(`ColourLayers.symbols`) the glass inside the frame is paper, so each pane is a thin,
straight hole in the ink. Panes end to end are one window. A strip is a window when:
- a traced wall runs beside it (within `WALL_REACH_PX`), along most of its length: a
  strip on its own is a shelf or a counter;
- one of its long sides is not room fill: windows face the outside. A page without
  fills (a grey scan) passes this test everywhere.
The window lies on its wall's centre line: the line of ink beside or under the frame
that runs on past both of its ends. Often that is the frame's own outer line, so the
carve (what is not traced as wall) leaves the pixel either side of it alone.

Pure: masks in, dataclasses out.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from app.domain.geometry import Point
from app.ingest.rooms import Mask

PANE_ACROSS_PX = (2, 6)  # glass between the frame's lines; 1 px gaps are double lines
PANE_ASPECT = 2.0  # a pane is a strip, not a square
PANE_FILL = 0.6  # a pane fills its box: a straight hole, not a crooked gap
MULLION_PX = 4  # panes of one window are at most this far apart, end to end
PANE_OFFSET_PX = 2  # and this far off one line
WINDOW_ASPECT = 2.5
WALL_REACH_PX = 4  # a window's wall is this close to its frame
WALL_ALONG = 0.6  # and runs along this share of its length
OUTSIDE_PX = 3  # the band beyond a long side that is read for fill
OUTSIDE_FILL = 0.35  # at most this much fill on the outside
BEYOND_PX = 6  # the wall line is read this far past each end of the frame
WALL_LINE_SHARE = 0.6  # and has ink along this share of it
KEEP_PX = 1  # the carve keeps the wall's centre line and this much either side


@dataclass(frozen=True)
class Window:
    a: Point  # the frame's ends, on the wall's centre line
    b: Point
    thickness_px: int  # the frame across the wall
    box: tuple[int, int, int, int]  # the frame: first and last column, first and last row


@dataclass(frozen=True)
class _Pane:
    x0: int
    y0: int
    x1: int
    y1: int
    horizontal: bool


def find_windows(symbols: Mask, fills: Mask, walls: Mask, min_length_px: int) -> list[Window]:
    """Windows at least `min_length_px` long. `walls` is the traced walls as a mask."""
    windows = []
    for group in _strips(_panes(symbols)):
        # The frame: the panes' glass and one frame line round it.
        x0, y0 = min(p.x0 for p in group) - 1, min(p.y0 for p in group) - 1
        x1, y1 = max(p.x1 for p in group) + 1, max(p.y1 for p in group) + 1
        horizontal = group[0].horizontal
        length, across = (x1 - x0 + 1, y1 - y0 + 1) if horizontal else (y1 - y0 + 1, x1 - x0 + 1)
        if length < min_length_px or length < WINDOW_ASPECT * across:
            continue
        box = (x0, y0, x1, y1)
        if not _outside(fills, box, horizontal):
            continue
        if not _along_wall(walls, box, horizontal):
            continue
        centre = _wall_line(symbols, box, horizontal)
        if horizontal:
            a, b = (float(x0), centre), (float(x1), centre)
        else:
            a, b = (centre, float(y0)), (centre, float(y1))
        windows.append(Window(a, b, across, box))
    return windows


def window_carve(windows: list[Window], shape: tuple[int, ...]) -> Mask:
    """The windows' frames and glass, drawn as windows and so not traced as walls; the wall
    line under a frame is kept."""
    carve = np.zeros(shape[:2], dtype=bool)
    rows, cols = np.arange(shape[0]), np.arange(shape[1])
    for w in windows:
        x0, y0, x1, y1 = w.box
        box = np.zeros(shape[:2], dtype=bool)
        box[max(0, y0) : y1 + 1, max(0, x0) : x1 + 1] = True
        if w.a[1] == w.b[1]:  # horizontal: the wall is a row
            box[np.abs(rows - w.a[1]) <= KEEP_PX] = False
        else:
            box[:, np.abs(cols - w.a[0]) <= KEEP_PX] = False
        carve |= box
    return carve


def _panes(symbols: Mask) -> list[_Pane]:
    """Thin straight holes in the symbols: the glass of a window's panes."""
    paper = (~symbols).astype(np.uint8)
    _, _, stats, _ = cv2.connectedComponentsWithStats(paper, connectivity=4)
    height, width = symbols.shape
    lo, hi = PANE_ACROSS_PX
    panes = []
    for x, y, w, h, area in stats[1:]:
        if x == 0 or y == 0 or x + w == width or y + h == height:
            continue  # open to the page's edge: not a hole
        across, along = min(w, h), max(w, h)
        if lo <= across <= hi and along >= PANE_ASPECT * across and area >= PANE_FILL * w * h:
            panes.append(_Pane(int(x), int(y), int(x + w - 1), int(y + h - 1), bool(w >= h)))
    return panes


def _strips(panes: list[_Pane]) -> list[list[_Pane]]:
    """Panes end to end along one line, one group per window."""
    groups: list[list[_Pane]] = []
    for p in sorted(panes, key=lambda p: (p.x0, p.y0) if p.horizontal else (p.y0, p.x0)):
        for group in groups:
            q = group[-1]
            if q.horizontal != p.horizontal:
                continue
            if p.horizontal:
                offset, gap = abs((q.y0 + q.y1) - (p.y0 + p.y1)) / 2, p.x0 - q.x1 - 1
            else:
                offset, gap = abs((q.x0 + q.x1) - (p.x0 + p.x1)) / 2, p.y0 - q.y1 - 1
            if offset <= PANE_OFFSET_PX and 0 <= gap <= MULLION_PX:
                group.append(p)
                break
        else:
            groups.append([p])
    return groups


def _outside(fills: Mask, box: tuple[int, int, int, int], horizontal: bool) -> bool:
    """One long side of the frame is mostly not room fill."""
    x0, y0, x1, y1 = box
    if horizontal:
        sides = [fills[max(0, y0 - OUTSIDE_PX) : y0, x0 : x1 + 1],
                 fills[y1 + 1 : y1 + 1 + OUTSIDE_PX, x0 : x1 + 1]]  # fmt: skip
    else:
        sides = [fills[y0 : y1 + 1, max(0, x0 - OUTSIDE_PX) : x0],
                 fills[y0 : y1 + 1, x1 + 1 : x1 + 1 + OUTSIDE_PX]]  # fmt: skip
    return any(side.size == 0 or float(side.mean()) <= OUTSIDE_FILL for side in sides)


def _along_wall(walls: Mask, box: tuple[int, int, int, int], horizontal: bool) -> bool:
    """A traced wall lies within `WALL_REACH_PX` of the frame along most of its length."""
    x0, y0, x1, y1 = box
    reach = WALL_REACH_PX
    if horizontal:
        along = walls[max(0, y0 - reach) : y1 + reach + 1, x0 : x1 + 1].any(axis=0)
    else:
        along = walls[y0 : y1 + 1, max(0, x0 - reach) : x1 + reach + 1].any(axis=1)
    return along.size > 0 and float(along.mean()) >= WALL_ALONG


def _wall_line(symbols: Mask, box: tuple[int, int, int, int], horizontal: bool) -> float:
    """The across position of the wall: the rows (or columns) whose ink runs on past both
    ends of the frame, starting within `WALL_REACH_PX` of it and followed outwards
    across a band's full thickness. The frame's middle when there are none."""
    x0, y0, x1, y1 = box
    view = symbols if horizontal else symbols.T
    (s0, s1), (a0, a1) = ((x0, x1), (y0, y1)) if horizontal else ((y0, y1), (x0, x1))
    ends = np.concatenate(
        [view[:, max(0, s0 - BEYOND_PX) : s0], view[:, s1 + 1 : s1 + 1 + BEYOND_PX]], axis=1
    )
    if ends.shape[1] == 0:
        return (a0 + a1) / 2
    runs_on = ends.mean(axis=1) >= WALL_LINE_SHARE
    start = [i for i in range(max(0, a0 - WALL_REACH_PX), a1 + WALL_REACH_PX + 1)
             if i < len(runs_on) and runs_on[i]]  # fmt: skip
    lines = set(start)
    for i in start:  # grow each line outwards while the next row runs on too
        for step in (-1, 1):
            j = i + step
            while 0 <= j < len(runs_on) and runs_on[j] and j not in lines:
                lines.add(j)
                j += step
    return float(np.mean(sorted(lines))) if lines else (a0 + a1) / 2
