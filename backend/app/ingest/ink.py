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

Walls and rooms read the ink page: fills and annotations become paper. OCR reads the page
divided by the fill colour around each pixel, so a fill turns white while the soft edges
of letters drawn on it stay soft; whitening fills outright left jagged letters that
RapidOCR read far worse on colorful-34.

Pure: arrays in, arrays out.
"""

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
import numpy.typing as npt
from PIL import Image

from app.ingest.rooms import Gray, Mask, ink_mask

NEUTRAL_CHROMA = 24  # scanners tint black and grey by up to ~20 per channel
RED_OVER = 48  # red labels on colorful-34 exceed green and blue by 50+; yellow by < 32
DARK_BELOW = 160  # a black line over a fill stays below; the fills are 200+ and red ~158
FILL_WINDOW = 0.03  # share of the page's longest side: a few letter heights
MIN_WINDOW_PX = 15
PAPER = 255


@dataclass(frozen=True)
class ColourLayers:
    fills: Mask  # light colour areas: room fills, zone tints
    annotations: Mask  # red marks: height labels, leaders, markup
    ink_page: Gray  # the page's grey with fills and annotations made paper
    ocr_page: Gray  # the page's grey with each fill divided out

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
    return ColourLayers(fills, annotations, ink_page, _fills_divided_out(rgb, grey, fills))


def _fills_divided_out(rgb: npt.NDArray[Any], grey: Gray, fills: Mask) -> Gray:
    """The page's grey with every pixel near a fill divided by that fill's colour.

    Ink over a fill is the fill colour darkened, so dividing by the fill gives the ink on
    white paper. The fill colour is the brightest fill pixel per channel within a window
    a few letters wide; pixels with no fill in reach keep their grey.
    """
    if not fills.any():
        return grey
    size = max(MIN_WINDOW_PX, round(FILL_WINDOW * max(grey.shape))) | 1
    only_fills = np.where(fills[..., None], rgb, 0).astype(np.uint8)
    around = cv2.dilate(only_fills, np.ones((size, size), np.uint8))
    divided = np.round(np.minimum(rgb * (PAPER / np.maximum(around, 1)), PAPER))
    divided_grey = np.asarray(
        Image.fromarray(divided.astype(np.uint8), "RGB").convert("L"), dtype=np.uint8
    )
    return np.where(around.max(axis=2) > 0, divided_grey, grey).astype(np.uint8)
