"""Draw a redraw benchmark sheet over its image, enlarged, to check a truth file by eye (#131).

    uv run python -m eval.redraw_overlay <truth.json> <out.png> [--image photo.png] [--scale 3]

The image is enlarged by repeating pixels (nearest), so each source pixel stays a sharp
block and a wall can be judged against it to the pixel. Walls are tinted where
`redraw_render.wall_mask` fills each run, and each run's outline is drawn on top. Every
element carries its index in the truth file's list, with a letter for the list: w walls,
o openings, r rooms, t texts ("w17 sits 2 px too low").

A sheet coordinate x is the centre of source pixel x, as `wall_mask` fills it.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.domain.geometry import Point
from eval.redraw_render import wall_mask
from eval.redraw_sheet import Sheet, load_sheet

WALL = (230, 0, 230)  # magenta
WALL_ALPHA = 0.45
DOOR = (0, 160, 0)  # green
WINDOW = (0, 190, 210)  # cyan
ROOM = (255, 120, 0)  # orange
TEXT = (30, 30, 220)  # blue
HALO = (255, 255, 255)

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont


def draw_overlay(photo_rgb: np.ndarray, sheet: Sheet, scale: int) -> np.ndarray:
    """`photo_rgb` (height x width x 3, uint8) enlarged `scale` times, `sheet` drawn over it."""
    if scale < 1:
        raise ValueError("the scale is a whole number from 1")
    if photo_rgb.ndim != 3 or photo_rgb.shape[2] != 3:
        raise ValueError("the image is height x width x 3 (RGB)")
    height, width = photo_rgb.shape[:2]
    big = _enlarge(photo_rgb.astype(np.uint8), scale)
    if not (sheet.walls or sheet.openings or sheet.rooms or sheet.texts):
        return big

    walls = np.zeros((height, width), dtype=bool)
    for w in sheet.walls:  # one at a time: where two outlines overlap, all of it is wall
        walls |= wall_mask([w], width, height)
    tint = _enlarge(walls, scale)
    mixed = big.astype(np.float64)
    mixed[tint] = mixed[tint] * (1 - WALL_ALPHA) + np.array(WALL) * WALL_ALPHA
    image = Image.fromarray(np.round(mixed).astype(np.uint8))
    draw = ImageDraw.Draw(image)
    font, small = _font(4 * scale), _font(3 * scale + 1)
    line = max(1, scale // 2)

    def at(p: Point) -> tuple[float, float]:
        return (p[0] * scale + (scale - 1) / 2, p[1] * scale + (scale - 1) / 2)

    def label(xy: tuple[float, float], text: str, colour: tuple[int, int, int], f: Font) -> None:
        draw.text(xy, text, fill=colour, font=f, stroke_width=1, stroke_fill=HALO)

    for i, w in enumerate(sheet.walls):
        corners = [at(p) for p in w.polygon]
        draw.polygon(corners, outline=WALL, width=1)
        cx = sum(c[0] for c in corners) / len(corners)
        cy = sum(c[1] for c in corners) / len(corners)
        label((cx + 2, cy + 2), f"w{i}", WALL, small)

    for i, o in enumerate(sheet.openings):
        colour = DOOR if o.kind == "door" else WINDOW
        a, b = at(o.a), at(o.b)
        draw.line([a, b], fill=colour, width=line + 1)
        for end in (a, b):
            draw.ellipse([end[0] - line, end[1] - line, end[0] + line, end[1] + line], fill=colour)
        if o.hinge is not None:
            h = at(o.hinge)
            r = 2 * scale
            draw.ellipse([h[0] - r, h[1] - r, h[0] + r, h[1] + r], outline=colour, width=line)
            if o.toward is not None:
                draw.line([h, at(o.toward)], fill=colour, width=line)
        if o.toward is not None:
            t = at(o.toward)
            draw.rectangle([t[0] - line, t[1] - line, t[0] + line, t[1] + line], fill=colour)
        mid = ((a[0] + b[0]) / 2 + 3, (a[1] + b[1]) / 2 + 3)
        label(mid, f"o{i}{'d' if o.kind == 'door' else 'w'}", colour, small)

    for i, room in enumerate(sheet.rooms):
        if room.polygon is not None:
            draw.polygon([at(p) for p in room.polygon], outline=ROOM, width=line)
        x, y = at(room.label)
        draw.line([(x - 2 * scale, y), (x + 2 * scale, y)], fill=ROOM, width=line)
        draw.line([(x, y - 2 * scale), (x, y + 2 * scale)], fill=ROOM, width=line)
        label((x + 2 * scale, y - 5 * scale), f"r{i} {room.name}", ROOM, font)

    for i, text in enumerate(sheet.texts):
        x, y = at(text.at)
        draw.rectangle([x - line, y - line, x + line, y + line], fill=TEXT)
        turned = " (90)" if text.rotation == 90 else ""
        label((x + 2, y + 2), f"t{i} {text.text}{turned}", TEXT, small)

    return np.asarray(image)


def _enlarge(pixels: np.ndarray, scale: int) -> np.ndarray:
    return np.repeat(np.repeat(pixels, scale, axis=0), scale, axis=1)


def _font(size: int) -> Font:
    """DejaVu Sans where installed (it draws "ö"); Pillow's own font otherwise."""
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("truth", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--image", type=Path, help="default: the .png next to the truth file")
    parser.add_argument("--scale", type=int, default=3)
    args = parser.parse_args(argv)

    image_path = args.image or _image_beside(args.truth)
    photo = np.asarray(Image.open(image_path).convert("RGB"))
    height, width = photo.shape[:2]
    try:
        sheet = load_sheet(json.loads(args.truth.read_text(encoding="utf-8")), width, height)
    except ValueError as e:
        print(f"{args.truth}: {e}", file=sys.stderr)
        return 1
    Image.fromarray(draw_overlay(photo, sheet, args.scale)).save(args.out)
    print(f"wrote {args.out}")
    return 0


def _image_beside(truth: Path) -> Path:
    """colorful-34.truth.json -> colorful-34.png"""
    return truth.with_name(truth.name.split(".")[0] + ".png")


if __name__ == "__main__":
    sys.exit(main())
