"""One page in, named polygons out: crop, enlarge, run the network, build polygons."""

import logging
import time
from typing import Any

import cv2
import numpy as np

from app.crop import drawing_box, has_frame, scale_for
from app.model import SPLIT, FloorplanModel
from app.shapes import from_components, from_polygons

log = logging.getLogger(__name__)


def analyse(model: FloorplanModel, rgb: np.ndarray) -> dict[str, Any]:
    """Polygons in original-image pixels, plus how the page was read."""
    from floortrans.post_prosessing import get_polygons, split_prediction

    started = time.monotonic()
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    framed = has_frame(gray)
    x0, y0, x1, y1 = drawing_box(gray)
    scale = scale_for(framed)
    drawing = rgb[y0:y1, x0:x1]
    if scale != 1.0:
        size = (round(drawing.shape[1] * scale), round(drawing.shape[0] * scale))
        drawing = cv2.resize(drawing, size, interpolation=cv2.INTER_CUBIC)
    h, w = drawing.shape[:2]
    heatmaps, rooms, icons = split_prediction(model.predict(drawing), (h, w), SPLIT)
    method = "cubicasa"
    try:
        polygons, types, room_polys, room_types = get_polygons(
            (heatmaps, rooms, icons), 0.2, [1, 2]
        )
        result = from_polygons(polygons, types, room_polys, room_types, scale, (x0, y0))
    except Exception:  # their post-processing has edge cases (IndexError seen with fp16)
        log.warning("CubiCasa post-processing failed; using connected regions", exc_info=True)
        method = "components"
        result = from_components(rooms.argmax(0), icons.argmax(0), scale, (x0, y0))
    return {
        **result,
        "crop": [x0, y0, x1, y1],
        "scale": scale,
        "framed": framed,
        "method": method,
        "seconds": round(time.monotonic() - started, 1),
    }
