"""2D geometry helpers. Page coordinates are rendered-image pixels, y pointing down.
Plan coordinates are millimetres, y pointing up (the way IFC expects them).
"""

import math

BBox = tuple[float, float, float, float]  # x0, y0, x1, y1
Point = tuple[float, float]


def bbox_union(a: BBox, b: BBox) -> BBox:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def bbox_area(b: BBox) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def bbox_iou(a: BBox, b: BBox) -> float:
    inter = bbox_area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))
    union = bbox_area(a) + bbox_area(b) - inter
    return inter / union if union > 0 else 0.0


def bbox_center(b: BBox) -> Point:
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def scale_bbox(b: BBox, factor: float) -> BBox:
    return (b[0] * factor, b[1] * factor, b[2] * factor, b[3] * factor)


def unrotate_bbox_cw90(b: BBox, original_height: float) -> BBox:
    """Map a box found in an image rotated 90° clockwise back to the original image.

    Rotating clockwise sends original (x, y) to (H - y, x), where H is the original
    height. The inverse is x = y', y = H - x'.
    """
    x0, y0, x1, y1 = b
    return (y0, original_height - x1, y1, original_height - x0)


def polygon_area(points: list[Point]) -> float:
    """Shoelace formula; absolute area, works for either winding."""
    n = len(points)
    if n < 3:
        return 0.0
    twice = sum(
        points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
        for i in range(n)
    )
    return abs(twice) / 2


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def px_to_plan_mm(p: Point, mm_per_px: float, page_height_px: float) -> Point:
    """Page pixel -> plan millimetres, flipping y so it points up."""
    return (p[0] * mm_per_px, (page_height_px - p[1]) * mm_per_px)


def footprint_mm(polygon_px: list[Point], mm_per_px: float, page_height_px: float) -> list[Point]:
    """Page polygon (pixels) -> plan polygon (millimetres)."""
    return [px_to_plan_mm(p, mm_per_px, page_height_px) for p in polygon_px]


def bbox_to_plan_polygon(b: BBox, mm_per_px: float, page_height_px: float) -> list[Point]:
    """Rectangle footprint (counter-clockwise in plan coordinates) of a page box."""
    x0, y0, x1, y1 = b
    return footprint_mm([(x0, y1), (x1, y1), (x1, y0), (x0, y0)], mm_per_px, page_height_px)
