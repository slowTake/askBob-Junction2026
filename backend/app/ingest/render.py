"""Render CAD shapes to a page image, so DXF documents get a viewer page and citations."""

import io
import logging
import os
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from app.domain.geometry import BBox, Point
from app.ingest.dxf_shapes import Shape

log = logging.getLogger(__name__)

MAX_SIDE_PX = 3000
MARGIN_PX = 40
WALL_FILL = (150, 150, 150)
ROOM_LINE = (200, 200, 200)

# Pillow's built-in font is ASCII-only: "Séjour" came out as "S☐jour". These cover Latin,
# Greek and Cyrillic. Docker and CI install the first (fonts-dejavu-core).
FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Debian, Ubuntu
    "/usr/share/fonts/TTF/DejaVuSans.ttf",  # Arch (ttf-dejavu)
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",  # Arch (noto-fonts)
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",  # Debian (fonts-noto-core)
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",  # macOS
)


@lru_cache
def font_path() -> str | None:
    path = next((p for p in FONT_CANDIDATES if os.path.isfile(p)), None)
    if path is None:
        log.warning("no Unicode font found: accented letters will be drawn as boxes")
    return path


@lru_cache(maxsize=128)
def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = font_path()
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)


@dataclass(frozen=True)
class PageFrame:
    """Maps plan millimetres (y up) to page pixels (y down)."""

    min_x: float
    max_y: float
    px_per_mm: float
    width_px: int
    height_px: int

    def to_px(self, p: Point) -> Point:
        return (
            (p[0] - self.min_x) * self.px_per_mm + MARGIN_PX,
            (self.max_y - p[1]) * self.px_per_mm + MARGIN_PX,
        )

    def bbox_px(self, points: list[Point]) -> BBox:
        px = [self.to_px(p) for p in points]
        xs, ys = [p[0] for p in px], [p[1] for p in px]
        return (min(xs), min(ys), max(xs), max(ys))


def frame_for(points: list[Point]) -> PageFrame:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    width_mm = max(max(xs) - min(xs), 1.0)
    height_mm = max(max(ys) - min(ys), 1.0)
    scale = (MAX_SIDE_PX - 2 * MARGIN_PX) / max(width_mm, height_mm)
    return PageFrame(
        min(xs), max(ys), scale,
        round(width_mm * scale) + 2 * MARGIN_PX, round(height_mm * scale) + 2 * MARGIN_PX,
    )  # fmt: skip


def render_png(items: list[Shape], frame: PageFrame) -> bytes:
    image = Image.new("RGB", (frame.width_px, frame.height_px), "white")
    draw = ImageDraw.Draw(image)
    for shape in sorted(items, key=_z_order):
        pts = [frame.to_px(p) for p in shape.points]
        if shape.text is not None:
            size = max(10, round(shape.text_height_mm * frame.px_per_mm))
            draw_text(draw, pts[0], shape.text, size, centred=False)
        elif shape.role == "wall" and shape.closed and len(pts) > 2:
            draw.polygon(pts, fill=WALL_FILL, outline="black")
        elif len(pts) > 1:
            color = ROOM_LINE if shape.role in ("room", "unit") else "black"
            draw.line(pts + ([pts[0]] if shape.closed else []), fill=color, width=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _z_order(shape: Shape) -> int:
    return {"room": 0, "unit": 0, "wall": 1}.get(shape.role or "", 2) + (shape.text is not None)


SUPERSCRIPTS = {"²": "2", "³": "3"}


def draw_text(
    draw: ImageDraw.ImageDraw, xy: Point, text: str, size: int, centred: bool = True
) -> None:
    """Draw text; "m²"/"m³" get a raised digit (the fallback font has no ² glyph).

    centred: xy is the middle of the text; otherwise xy is its left end on the baseline.
    """
    regular = font(size)
    small = font(max(6, int(size * 0.6)))
    parts = [(SUPERSCRIPTS[ch], small) if ch in SUPERSCRIPTS else (ch, regular) for ch in text]
    width = sum(draw.textlength(ch, font=f) for ch, f in parts)
    x, y = xy
    if centred:
        x, y = x - width / 2, y + size * 0.35  # baseline sits a third below the middle
    for ch, f in parts:
        dy = -size * 0.35 if f is small else 0.0
        draw.text((x, y + dy), ch, fill="black", font=f, anchor="ls")
        x += draw.textlength(ch, font=f)
