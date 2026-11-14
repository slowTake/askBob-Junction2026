"""One page in, named polygons out: crop, size to the budget, run the network, build polygons."""

import logging
import time
from typing import Any

import cv2
import numpy as np

from app.budget import plan_for
from app.crop import drawing_box, has_frame, scale_for
from app.model import SPLIT, FloorplanModel
from app.shapes import Result, from_components, from_polygons

log = logging.getLogger(__name__)
BUDGET_PX = 16e6  # most pixels the network reads per page: about 1 GB of labels at peak
DETAILED_PX = 4e6  # CubiCasa's polygon step keeps 44 float maps: ~0.7 GB at this size


def analyse(model: FloorplanModel, rgb: np.ndarray) -> dict[str, Any]:
    """Polygons in original-image pixels, plus how the page was read.

    Any upload size is safe: the network never reads more than BUDGET_PX, and a
    drawing too dense to read within it is skipped (`method: "skipped_too_large"`).
    """
    started = time.monotonic()
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    framed = has_frame(gray)
    x0, y0, x1, y1 = drawing_box(gray)
    plan = plan_for(x1 - x0, y1 - y0, scale_for(framed), BUDGET_PX, DETAILED_PX)
    info: dict[str, Any] = {"crop": [x0, y0, x1, y1], "framed": framed}
    if plan is None:
        empty: Result = {"rooms": [], "walls": [], "objects": []}
        return {**empty, **info, "scale": None, "method": "skipped_too_large", "seconds": 0.0}

    drawing = rgb[y0:y1, x0:x1]
    if plan.scale != 1.0:
        size = (round(drawing.shape[1] * plan.scale), round(drawing.shape[0] * plan.scale))
        shrink = plan.scale < 1.0
        drawing = cv2.resize(
            drawing, size, interpolation=cv2.INTER_AREA if shrink else cv2.INTER_CUBIC
        )
    offset = (x0, y0)
    if plan.detailed:
        result, method = _detailed(model, drawing, plan.scale, offset)
    else:
        rooms, icons = model.predict_labels(drawing)
        result, method = from_components(rooms, icons, plan.scale, offset), "labels"
    return {
        **result,
        **info,
        "scale": round(plan.scale, 3),
        "method": method,
        "seconds": round(time.monotonic() - started, 1),
    }


def _detailed(
    model: FloorplanModel, drawing: np.ndarray, scale: float, offset: tuple[int, int]
) -> tuple[Result, str]:
    """All 44 channels and CubiCasa's polygon step: cleaner shapes, small pages only."""
    from floortrans.post_prosessing import get_polygons, split_prediction

    h, w = drawing.shape[:2]
    heatmaps, rooms, icons = split_prediction(model.predict(drawing), (h, w), SPLIT)
    try:
        polygons, types, room_polys, room_types = get_polygons(
            (heatmaps, rooms, icons), 0.2, [1, 2]
        )
        return from_polygons(polygons, types, room_polys, room_types, scale, offset), "cubicasa"
    except Exception:  # their post-processing has edge cases (IndexError seen with fp16)
        log.warning("CubiCasa post-processing failed; using connected regions", exc_info=True)
        return from_components(rooms.argmax(0), icons.argmax(0), scale, offset), "components"
