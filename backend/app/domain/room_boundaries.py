"""Validate a candidate room boundary against the printed room labels on its page."""

from collections.abc import Sequence

from app.domain.geometry import Point
from app.domain.polygons import point_in_polygon


def holds_one_room(polygon: list[Point], own: Point, others: Sequence[Point]) -> bool:
    """A room outline must contain its own label and none of its neighbours' labels.

    Model segmentation and flood fills can both join rooms through open doors.
    Without a printed area or physical scale, the other labels still prove that
    such a polygon describes several rooms rather than this one.
    """
    return point_in_polygon(own, polygon) and not any(
        point_in_polygon(point, polygon) for point in others
    )
