"""Separate a page's colours before thresholding: line work, fills and red annotations.

Raster ingest used to turn a page grey and threshold it, so on a coloured scan a blue
ceiling zone (grey ~203) became wall ink and red height labels became lines. Each pixel
is sorted first (D-050):

- neutral (channels within `NEUTRAL_CHROMA` of each other): left as it is, so a black
  and white scan gives exactly the grey page it gave before;
- red (red above green and blue by `RED_OVER`): an annotation, read but never a wall;
- any other colour darker than `DARK_BELOW` in grey: ink, e.g. a black line blended
  with the fill under it, or dark pen;
- any other colour: a fill (room colour, zone tint), which is paper to walls and OCR.

Pure: arrays in, arrays out.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
from PIL import Image

from app.ingest.rooms import Gray, Mask, ink_mask

NEUTRAL_CHROMA = 24  # scanners tint black and grey by up to ~20 per channel
RED_OVER = 48  # red labels on colorful-34 exceed green and blue by 50+; yellow by < 32
DARK_BELOW = 160  # a black line over a fill stays below; the fills are 200+ and red ~158
PAPER = 255


@dataclass(frozen=True)
class ColourLayers:
    fills: Mask  # light colour areas: room fills, zone tints
    annotations: Mask  # red marks: height labels, leaders, markup
    ink_page: Gray  # the page's grey with fills and annotations made paper
    ocr_page: Gray  # the page's grey with fills made paper and annotations darkened

    @property
    def ink(self) -> Mask:
        """The line work: walls, lines and black text (Otsu on the ink page)."""
        return ink_mask(self.ink_page)


def separate_colours(rgb: npt.NDArray[Any]) -> ColourLayers:
    """Split an RGB page (uint8, H x W x 3) into its colour layers."""
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    grey = np.asarray(Image.fromarray(rgb, "RGB").convert("L"), dtype=np.uint8)
    channels = rgb.astype(np.int16)
    high, low = channels.max(axis=2), channels.min(axis=2)
    red = channels[..., 0] - np.maximum(channels[..., 1], channels[..., 2])
    coloured = high - low >= NEUTRAL_CHROMA
    annotations = coloured & (red >= RED_OVER)
    fills = coloured & ~annotations & (grey >= DARK_BELOW)
    ink_page = np.where(fills | annotations, PAPER, grey).astype(np.uint8)
    # A red label's darkest channel (green or blue) is darker than its grey: OCR then
    # sees it with the contrast of black text.
    ocr_page = np.where(fills, PAPER, np.where(annotations, low, grey)).astype(np.uint8)
    return ColourLayers(fills, annotations, ink_page, ocr_page)
