import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from app.domain.redraw_mode import PLAN_MODE, SKETCH_MODE, redraw_mode
from app.ingest.ink import separate_colours
from app.ingest.page_stats import page_stats, paper_spread, straight_share

BENCH = Path(__file__).resolve().parents[2] / "eval" / "redraw_bench"


def test_long_straight_runs_count_and_diagonals_do_not() -> None:
    ink = np.zeros((100, 100), np.bool_)
    ink[10:12, 10:90] = True  # a wall 80 px long, 2 thick: 160 px
    for i in range(50, 100):
        ink[i, i] = True  # a diagonal, 50 px, no run of 2 in either direction
    # The run must be 10 % of the longest side, 10 px, made odd: 11 px. The wall's
    # 160 px pass, the diagonal's 50 do not: 160 / 210.
    assert math.isclose(straight_share(ink), 160 / 210)


def test_vertical_runs_count_and_short_dashes_do_not() -> None:
    ink = np.zeros((100, 100), np.bool_)
    ink[20:60, 50] = True  # vertical, 40 px
    ink[80, 10:19] = True  # a dash of 9 px, under the 11 px run
    assert math.isclose(straight_share(ink), 40 / 49)


def test_a_blank_page_has_no_straight_share() -> None:
    assert straight_share(np.zeros((30, 40), np.bool_)) == 0.0


def test_small_pages_still_need_a_nine_pixel_run() -> None:
    ink = np.zeros((40, 40), np.bool_)
    ink[5, 0:8] = True  # 10 % of 40 is 4 px, but runs shorter than 9 px are letters
    ink[10, 0:9] = True
    assert math.isclose(straight_share(ink), 9 / 17)


def test_paper_in_shadow_spreads_its_brightness() -> None:
    grey = np.full((80, 80), 255, np.uint8)
    grey[:, 40:] = 200  # the right half in shadow
    # 8 x 8 cells of 10 px: 32 cells at 255, 32 at 200. Between the 5th and 95th
    # percentile of the cells (linear, 63 gaps: positions 3.15 and 59.85): 255 - 200.
    assert paper_spread(grey) == 55.0


def test_ink_on_even_paper_is_not_a_shadow() -> None:
    grey = np.full((80, 80), 255, np.uint8)
    grey[::20, :] = 0  # a line every 20 rows: 1 row in 10 of the cells that have one
    # A cell's paper is its 90th percentile: 9 of its 10 rows are paper, so 255.
    assert paper_spread(grey) == 0.0


def test_a_page_smaller_than_the_grid_has_no_spread() -> None:
    grey = np.full((4, 4), 255, np.uint8)
    grey[:, 2:] = 0  # fewer pixels than 8 x 8 cells: nothing to compare
    assert paper_spread(grey) == 0.0


def test_page_stats_read_the_colour_layers() -> None:
    rgb = np.full((100, 100, 3), 255, np.uint8)
    rgb[:20, :] = (240, 240, 144)  # a yellow room fill over the top 20 rows: 20 %
    rgb[50:52, 10:90] = 0  # one black wall, 160 px, all straight
    stats = page_stats(separate_colours(rgb), dimension_words=4)
    assert math.isclose(stats.fill_share, 0.2)
    assert math.isclose(stats.straight_share, 1.0)
    assert stats.dimension_words == 4
    # Fills are paper on the ink page, so the page is evenly white.
    assert stats.paper_spread == 0.0


def test_colorful_34_gets_the_page_redraw() -> None:
    # The benchmark's scanned printed plan (D-049): colour fills over half the page,
    # ruled walls, a flat scan. Plan from its pixels alone, before any OCR is counted.
    rgb = np.asarray(Image.open(BENCH / "colorful-34.png").convert("RGB"))
    stats = page_stats(separate_colours(rgb), dimension_words=0)
    assert stats.fill_share > 0.5
    assert redraw_mode("image", stats) == PLAN_MODE


def test_a_photographed_hand_sketch_keeps_the_sketch_redraw() -> None:
    # No photo of a hand drawing is in the repository, so this one is drawn: freehand
    # pen lines on off-white paper, a few degrees off the axes, a shadow across the page.
    stats = page_stats(separate_colours(_napkin()), dimension_words=0)
    assert stats.fill_share == 0.0
    assert stats.straight_share < 0.35
    assert stats.paper_spread >= 30.0
    assert redraw_mode("image", stats) == SKETCH_MODE


def _napkin(width: int = 1600, height: int = 1200) -> np.ndarray:
    """Four walls and two partitions, wobbling by up to 11 px, turned 3 degrees, drawn
    with a 5 px pen on paper that darkens from 235 to 175 toward the bottom right."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
    paper = 235 - 60 * (xx / width) * (yy / height)
    tint = np.dstack([paper, paper * 0.98, paper * 0.93])  # warm paper, chroma under 24
    image = Image.fromarray(np.clip(tint, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(image)
    turn = math.radians(3)

    def turned(x: float, y: float) -> tuple[float, float]:
        cx, cy = width / 2, height / 2
        return (
            cx + (x - cx) * math.cos(turn) - (y - cy) * math.sin(turn),
            cy + (x - cx) * math.sin(turn) + (y - cy) * math.cos(turn),
        )

    lines = [((250, 200), (1350, 200)), ((1350, 200), (1350, 1000)),
             ((1350, 1000), (250, 1000)), ((250, 1000), (250, 200)),
             ((800, 200), (800, 1000)), ((250, 600), (800, 600))]  # fmt: skip
    for n, ((x0, y0), (x1, y1)) in enumerate(lines):
        nx, ny = y0 - y1, x1 - x0
        length = math.hypot(nx, ny)
        points = []
        for i in range(81):
            t = i / 80
            off = 8 * math.sin(t * 2.3 * math.pi + n) + 3 * math.sin(t * 23 + 2 * n)
            points.append(turned(x0 + (x1 - x0) * t + off * nx / length,
                                 y0 + (y1 - y0) * t + off * ny / length))  # fmt: skip
        draw.line(points, fill=(40, 40, 55), width=5, joint="curve")
    return np.asarray(image)
