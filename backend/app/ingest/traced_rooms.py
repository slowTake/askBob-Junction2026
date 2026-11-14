"""Room outlines traced from a page's own lines, sized for the page (D-024)."""

from collections.abc import Sequence

from app.domain.geometry import Point
from app.domain.room_faces import room_outlines, to_wall_face
from app.domain.tokens import Word
from app.ingest.line_trace import page_lines
from app.ingest.rooms import Gray

# Measured on 150 DPI Swiss sheets; other resolutions scale with DPI.
REFERENCE_DPI = 150.0
MIN_ROOM_PX = 1500  # ~0.4 m² at 1:100: smaller faces are fixtures or symbols
MIN_WIDTH_PX = 18  # thinner faces are wall interiors or hatching
EDGE_PX = 2.0  # traced outlines sit this far inside the wall face
MAX_ROOM_FRAC = 0.5  # the page around the building; leaks are caught by the one-label rule


def traced_outlines(
    gray: Gray, words: Sequence[Word], label_points: Sequence[Point], dpi: float | None
) -> list[list[Point] | None]:
    """For each room label, the outline of the room around it, or None."""
    if not label_points:
        return []
    f = (dpi or REFERENCE_DPI) / REFERENCE_DPI
    lines = page_lines(gray, [(w.text, w.bbox) for w in words])
    outlines = room_outlines(
        lines,
        label_points,
        min_area_px=MIN_ROOM_PX * f * f,
        min_width_px=MIN_WIDTH_PX * f,
        max_area_px=MAX_ROOM_FRAC * gray.shape[0] * gray.shape[1],
    )
    return [to_wall_face(o, EDGE_PX * f) if o else None for o in outlines]
