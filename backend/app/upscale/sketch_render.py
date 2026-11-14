"""Draw a sketch draft as a PNG, so the model can compare it with the photo.

The shapes are the ones stored for the frontend (app/domain/sketch_drawing.py), so
the model checks what the user will see. Black on white, at the size of the image
the model was sent.
"""

import io
from collections.abc import Sequence

from PIL import Image, ImageDraw, ImageFont

from app.domain.sketch_drawing import Shape

INK = (20, 20, 20)
PAPER = (255, 255, 255)
LINE_SHARE = 0.002  # door and window lines, as a share of the longer side


def render_png(
    shapes: Sequence[Shape], page_w: float, page_h: float, width: int, height: int
) -> bytes:
    """The shapes (page pixels) drawn on a `width` x `height` image."""
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)
    fx, fy = width / page_w, height / page_h
    line = max(1, round(LINE_SHARE * max(width, height)))

    def px(points: Sequence[Sequence[float]]) -> list[tuple[float, float]]:
        return [(p[0] * fx, p[1] * fy) for p in points]

    for s in shapes:
        props = s.properties
        if s.kind == "wall":
            for piece in props["pieces_px"]:
                draw.polygon(px(piece), fill=INK)
        elif s.kind == "door":
            draw.line(px(props["leaf_px"]), fill=INK, width=line)
            draw.line(px(props["arc_px"]), fill=INK, width=max(1, line // 2), joint="curve")
        elif s.kind == "window":
            for segment in props["lines_px"]:
                draw.line(px(segment), fill=INK, width=max(1, line // 2))
        elif s.kind in ("room", "text") and s.text:
            (x, y), size = px([props["label_px"]])[0], props["font_px"] * fy
            font = ImageFont.load_default(size=max(6.0, size))
            draw.text((x, y), s.text, fill=INK, font=font, anchor="mm")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
