"""Room outlines from a drawing's line network, as CAD "boundary" tools find them (D-024).

Pure geometry on Shapely/GEOS: no images, no I/O. The reader traces the lines
(app/ingest/line_trace.py); these rules decide which enclosed faces are rooms and
which room each printed label names.
"""

from collections.abc import Sequence

import numpy as np
from shapely import STRtree
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

Coord = tuple[float, float]
MIN_PIECE_PX = 20  # faces smaller than this are tracing noise
SHARED_EDGE_PX = 2  # two faces touch if they share more boundary than this


def faces_from_lines(lines: Sequence[LineString], snap_px: float) -> list[Polygon]:
    """Every enclosed face of the line network.

    Line ends are extended by `snap_px` first, so a line that stops just short of
    another (a plotter or tracing gap) still closes the face; GEOS then splits lines
    where they cross and finds the faces.
    """
    if not lines:
        return []
    noded = unary_union([_extend(line, snap_px) for line in lines])
    return [p for p in polygonize(noded) if p.area > 0]


def room_outlines(
    lines: Sequence[LineString],
    label_points: Sequence[Coord],
    min_area_px: float,
    min_width_px: float,
    max_area_px: float = float("inf"),
    snap_px: float = 3.0,
) -> list[list[Coord] | None]:
    """For each room label, the outline of the room around it (or None).

    1. Faces too big to be a room (the page around the building) are dropped first,
       then thin faces: a wall band's ring or hatching vanishes under an inward
       buffer of half `min_width_px`; a room with furniture inside it does not.
    2. Furniture drawn inside a room is a face nested in the room's outline: dropped.
    3. A label goes to the largest face around it that holds no other label, so a
       room wins over the tub its number is written in, but never takes a
       neighbour's name.
    4. A face that touches exactly one labelled room and is smaller than it (a
       counter or tub closed against the walls) is part of that room. A face that
       touches two rooms (a doorway region) stays out. Walls are not faces, so rooms
       either side of a wall never touch.
    """
    pieces = [
        Polygon(f.exterior)
        for f in faces_from_lines(lines, snap_px)
        if f.area >= MIN_PIECE_PX
        and Polygon(f.exterior).area <= max_area_px
        and not f.buffer(-min_width_px / 2).is_empty
    ]
    pieces = _top_level(pieces)
    points = [Point(p) for p in label_points]
    held = [sum(1 for pt in points if piece.contains(pt)) for piece in pieces]
    room_of: list[int | None] = []
    for pt in points:
        around = [i for i, piece in enumerate(pieces) if piece.contains(pt)]
        alone = [i for i in around if held[i] <= 1]
        room_of.append(max(alone, key=lambda i: pieces[i].area) if alone else None)
    rooms = {i: pieces[i] for i in room_of if i is not None}
    _absorb(rooms, [p for i, p in enumerate(pieces) if i not in rooms])
    out: list[list[Coord] | None] = []
    for i in room_of:
        room = rooms.get(i) if i is not None else None
        ok = room is not None and min_area_px <= room.area <= max_area_px
        out.append(_coords(room) if ok and room is not None else None)
    return out


def to_wall_face(outline: Sequence[Coord], edge_px: float) -> list[Coord]:
    """Move a traced outline out onto the wall face, keeping sharp corners.

    Tracing puts the outline on the wall's ink pixels, about half a plotted line
    width inside the face (measured 1.6-2.5 px on 150 DPI Swiss sheets).
    """
    moved = Polygon(outline).buffer(edge_px, join_style="mitre")
    return _coords(moved) if isinstance(moved, Polygon) else list(outline)


def _top_level(pieces: list[Polygon]) -> list[Polygon]:
    """Drop pieces nested inside another piece's outline (furniture in a room)."""
    tree = STRtree(pieces)
    nested: set[int] = set()
    for i, piece in enumerate(pieces):
        for j in tree.query(piece, predicate="contains_properly"):
            if int(j) != i:
                nested.add(int(j))
    return [p for i, p in enumerate(pieces) if i not in nested]


def _absorb(rooms: dict[int, Polygon], loose: list[Polygon]) -> None:
    """Merge loose faces into the one room they touch, in rounds (a fixture next to
    an absorbed fixture joins the same room in the next round)."""
    taken: set[int] = set()
    changed = True
    while changed:
        changed = False
        for n, piece in enumerate(loose):
            if n in taken:
                continue
            touching = [k for k, room in rooms.items() if _shared(piece, room) > SHARED_EDGE_PX]
            if len(touching) == 1 and piece.area < rooms[touching[0]].area:
                rooms[touching[0]] = _merge(rooms[touching[0]], piece)
                taken.add(n)
                changed = True


def _shared(a: Polygon, b: Polygon) -> float:
    return float(a.boundary.intersection(b.boundary).length)


def _merge(a: Polygon, b: Polygon) -> Polygon:
    merged = unary_union([a, b]).buffer(0.5).buffer(-0.5)  # close hairline seams
    if merged.geom_type == "MultiPolygon":
        merged = max(merged.geoms, key=lambda g: g.area)
    return Polygon(merged.exterior)


def _coords(polygon: Polygon) -> list[Coord]:
    return [(float(x), float(y)) for x, y in list(polygon.exterior.coords)[:-1]]


def _extend(line: LineString, by: float) -> LineString:
    coords = np.asarray(line.coords, dtype=float)
    if len(coords) < 2 or by <= 0:
        return line
    for end, inner in ((0, 1), (-1, -2)):
        direction = coords[end] - coords[inner]
        length = float(np.hypot(*direction))
        if length > 0:
            coords[end] = coords[end] + direction / length * by
    return LineString(coords)
