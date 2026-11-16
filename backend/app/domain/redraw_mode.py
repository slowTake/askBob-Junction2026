"""Which redraw a page gets (#138): the page redraw ("plan") or the sketch redraw.

The page redraw (D-027) keeps ingest's elements, their dimensions and the scale, and adds
one vision pass's findings; it can be measured against the drawing's pixels. The sketch
redraw (D-028) has a model author the whole plan and measures nothing. A scanned printed
plan must get the first; a photo of a hand drawing the second.

Raster image pages are told apart by statistics ingest computes from their pixels and
stores in `page.meta["page_stats"]` (`app/ingest/page_stats.py`). A page is a plan when
any of these says it was printed:

- light colour fills cover `FILL_PLAN` of the page (room colours);
- OCR read `DIMENSION_WORDS_PLAN` dimension strings or more;
- `STRAIGHT_PLAN` of its ink lies in long horizontal or vertical runs, on paper as even
  as a scan's (a photo's shadow spreads the paper's brightness by `PAPER_PHOTO` or more;
  a carefully drawn sketch has straight lines too).

Everything else on an image is a sketch. Pages of other formats are always plans.
Pure: no I/O.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.sketch import SKETCH_KINDS, SKETCH_MODE
from app.domain.upscale import FILL_MODE, UPSCALE_FORMAT

PLAN_MODE = "plan"
REDRAW_MODES = (PLAN_MODE, SKETCH_MODE)
STATS_KEY = "page_stats"  # page.meta key

# colorful-34 (a scanned printed plan, eval/redraw_bench) measures 0.574 fills, 9 dimension
# words, 0.472 straight and a spread of 0; a synthetic phone photo of a freehand sketch
# 0, 0, 0.117 and 35.8 (page_stats_test.py). The cuts sit between with room on both sides.
FILL_PLAN = 0.05  # share of the page
DIMENSION_WORDS_PLAN = 3
STRAIGHT_PLAN = 0.35  # share of the ink
PAPER_PHOTO = 30.0  # grey levels between the darkest and brightest paper


@dataclass(frozen=True)
class PageStats:
    straight_share: float  # ink in horizontal or vertical runs of 10 % of the longest side
    fill_share: float  # page pixels that are light colour fills (app/ingest/ink.py)
    dimension_words: int  # OCR words read as dimensions
    paper_spread: float  # grey levels from the darkest to the brightest paper on the page


def redraw_mode(kind: str, stats: PageStats | None) -> str:
    """ "plan" or "sketch" for a page of a document of `kind` that looks like `stats`.

    Image pages without statistics (ingested before #138) are sketches, as before.
    """
    if kind not in SKETCH_KINDS:
        return PLAN_MODE
    if stats is None:
        return SKETCH_MODE
    printed = (
        stats.fill_share >= FILL_PLAN
        or stats.dimension_words >= DIMENSION_WORDS_PLAN
        or (stats.straight_share >= STRAIGHT_PLAN and stats.paper_spread < PAPER_PHOTO)
    )
    return PLAN_MODE if printed else SKETCH_MODE


def page_redraw_mode(kind: str, meta: Mapping[str, object]) -> str:
    """The mode a page is in: the redraw that ran on it, else the one it would get.

    A page with matched CAD rooms is a plan: its clean sheet is the CAD geometry (D-030).
    """
    entry = meta.get("upscale")
    if isinstance(entry, Mapping) and entry.get("format") == UPSCALE_FORMAT:
        return SKETCH_MODE if entry.get("mode", FILL_MODE) == SKETCH_MODE else PLAN_MODE
    if meta.get("companion_dxf"):
        return PLAN_MODE
    return redraw_mode(kind, stats_from_meta(meta.get(STATS_KEY)))


def stats_meta(stats: PageStats) -> dict[str, float | int]:
    """What `page.meta["page_stats"]` stores: shares to 3 decimals, the spread to 1."""
    return {
        "straight_share": round(stats.straight_share, 3),
        "fill_share": round(stats.fill_share, 3),
        "dimension_words": stats.dimension_words,
        "paper_spread": round(stats.paper_spread, 1),
    }


def stats_from_meta(raw: object) -> PageStats | None:
    """Read stored statistics; None when missing or malformed (never repaired)."""
    if not isinstance(raw, Mapping):
        return None
    straight, fill, spread = (
        _number(raw.get(k)) for k in ("straight_share", "fill_share", "paper_spread")
    )
    words = raw.get("dimension_words")
    if straight is None or fill is None or spread is None:
        return None
    if isinstance(words, bool) or not isinstance(words, int) or words < 0:
        return None
    return PageStats(straight, fill, words, spread)


def _number(v: object) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v) if v >= 0 else None
