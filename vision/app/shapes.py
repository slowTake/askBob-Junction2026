"""Turn the model's output into named polygons in original-image pixels.

`from_polygons` takes CubiCasa's post-processing output; `from_components` is the
fallback straight from the class maps when that post-processing fails.
"""

from typing import Any

import cv2
import numpy as np

from app.tiles import to_original

ROOMS = ["Background", "Outdoor", "Wall", "Kitchen", "Living Room", "Bed Room", "Bath",
         "Entry", "Railing", "Storage", "Garage", "Undefined"]  # fmt: skip
ICONS = ["No Icon", "Window", "Door", "Closet", "Electrical Appliance", "Toilet", "Sink",
         "Sauna Bench", "Fire Place", "Bathtub", "Chimney"]  # fmt: skip
NOT_ROOMS = {"Background", "Wall", "Railing"}

Result = dict[str, list[Any]]


def from_polygons(
    polygons: list[Any],
    types: list[dict[str, Any]],
    room_polygons: list[Any],
    room_types: list[dict[str, Any]],
    scale: float,
    offset: tuple[float, float],
) -> Result:
    walls: list[Any] = []
    objects: list[dict[str, Any]] = []
    for poly, t in zip(polygons, types, strict=True):
        points = to_original(np.asarray(poly).reshape(-1, 2), scale, offset)
        if t["type"] == "wall":
            walls.append(points)
        else:
            objects.append({"class": ICONS[int(t["class"])], "polygon": points})
    rooms = []
    for poly, t in zip(room_polygons, room_types, strict=True):
        for part in getattr(poly, "geoms", [poly]):  # a MultiPolygon: one room per piece
            if part.is_empty or not hasattr(part, "exterior"):
                continue
            points = to_original(list(part.exterior.coords)[:-1], scale, offset)
            rooms.append({"class": ROOMS[int(t["class"])], "polygon": points})
    return {"rooms": rooms, "walls": walls, "objects": objects}


def from_components(
    rooms: np.ndarray,
    icons: np.ndarray,
    scale: float,
    offset: tuple[float, float],
    min_area_px: int = 50,
) -> Result:
    """Each connected region of one class becomes a room outline, a wall or an object box.

    Door and window pixels count as wall when tracing rooms, so two rooms of the same
    type joined by a doorway stay two rooms.
    """
    result: Result = {"rooms": [], "walls": [], "objects": []}
    for index, name in enumerate(ICONS[1:], start=1):
        for x, y, w, h in _regions(icons == index, min_area_px):
            box = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
            result["objects"].append({"class": name, "polygon": to_original(box, scale, offset)})
    openings = np.isin(icons, [ICONS.index("Door"), ICONS.index("Window")])
    for index, name in enumerate(ROOMS):
        if name in ("Background", "Railing"):
            continue
        mask = (rooms == index) & ~openings if name != "Wall" else rooms == index
        for outline in _outlines(mask, min_area_px):
            points = to_original(outline, scale, offset)
            if name == "Wall":
                result["walls"].append(points)
            else:
                result["rooms"].append({"class": name, "polygon": points})
    return result


def _outlines(mask: np.ndarray, min_area_px: int) -> list[np.ndarray]:
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    return [
        cv2.approxPolyDP(c, 2.0, True).reshape(-1, 2)
        for c in contours
        if cv2.contourArea(c) >= min_area_px
    ]


def _regions(mask: np.ndarray, min_area_px: int) -> list[tuple[int, int, int, int]]:
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    return [
        (int(s[0]), int(s[1]), int(s[2]), int(s[3]))
        for s in stats[1:count]
        if s[cv2.CC_STAT_AREA] >= min_area_px
    ]
