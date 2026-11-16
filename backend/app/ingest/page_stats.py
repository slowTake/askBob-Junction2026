"""What a raster page looks like, measured at ingest to pick its redraw (#138).

`app/domain/redraw_mode.py` reads these to tell a scanned printed plan from a photo of
a hand drawing:

- straight share: printed walls are ruled and lie along the page's axes; a freehand
  line wobbles and leans, so it breaks into runs shorter than `RUN_SHARE` of the page;
- fill share: room colours, from the colour layers (`app/ingest/ink.py`);
- paper spread: a scan's paper is evenly white, a photo's has shadows. Each cell of an
  `CELLS` x `CELLS` grid gives its paper brightness as the 90th percentile of its grey
  (ink rarely covers a tenth of a cell); the spread is between the 5th and 95th
  percentile of the cells, so one dark corner or blank cell does not decide it.

The dimension words come from OCR and are counted by the caller. Pure: arrays in.
"""

import cv2
import numpy as np

from app.domain.redraw_mode import PageStats
from app.ingest.ink import ColourLayers
from app.ingest.rooms import Gray, Mask

RUN_SHARE = 0.10  # of the longest side: walls between doors are longer, wobbles shorter
MIN_RUN_PX = 9  # odd; on small pages, runs shorter than this are letters
CELLS = 8
PAPER_PERCENTILE = 90
SPREAD_PERCENTILES = (5, 95)


def page_stats(layers: ColourLayers, dimension_words: int) -> PageStats:
    return PageStats(
        straight_share=straight_share(layers.ink),
        fill_share=float(layers.fills.mean()) if layers.fills.size else 0.0,
        dimension_words=dimension_words,
        paper_spread=paper_spread(layers.ink_page),
    )


def straight_share(ink: Mask) -> float:
    """Share of the ink in horizontal or vertical runs of `RUN_SHARE` of the longest side."""
    total = int(ink.sum())
    if total == 0:
        return 0.0
    # Odd, so the opening is centred: an even kernel shifts and trims a pixel off a run.
    run = max(MIN_RUN_PX, round(RUN_SHARE * max(ink.shape))) | 1
    marks = ink.astype(np.uint8)

    def runs(kernel: tuple[int, int]) -> Mask:
        # Off the page is paper: by default OpenCV lets a run end on the edge.
        opened = cv2.morphologyEx(marks, cv2.MORPH_OPEN, np.ones(kernel, np.uint8),
                                  borderType=cv2.BORDER_CONSTANT, borderValue=0)  # fmt: skip
        return np.asarray(opened > 0)

    straight = (runs((1, run)) | runs((run, 1))) & ink
    return int(straight.sum()) / total


def paper_spread(grey: Gray) -> float:
    """Grey levels between the darker and brighter paper of the page (see above)."""
    height, width = grey.shape
    if height < CELLS or width < CELLS:
        return 0.0
    papers = [
        np.percentile(
            grey[i * height // CELLS : (i + 1) * height // CELLS,
                 j * width // CELLS : (j + 1) * width // CELLS],
            PAPER_PERCENTILE,
        )
        for i in range(CELLS)
        for j in range(CELLS)
    ]  # fmt: skip
    low, high = np.percentile(papers, SPREAD_PERCENTILES)
    return float(high - low)
