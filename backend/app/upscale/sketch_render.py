"""Draw a sketch draft as a PNG, so the model can compare it with the photo.

The shapes are the ones stored for the frontend (app/domain/sketch_drawing.py), so
the model checks what the user will see, at the size of the image the model was sent.
For a check round the draft is drawn in red over the photo: a wall beside its drawn
line shows as a red line next to a dark one, which two separate pictures hide.
"""

import io
from collections.abc import Sequence

from PIL import Image, ImageDraw, ImageFont

from app.domain.sketch_drawing import Shape

INK = (20, 20, 20)
OVER = (225, 30, 30)  # the draft over the photo
PAPER = (255, 255, 255)
MIN_CONTRAST = 60  # grey levels between ink and paper, or nothing counts as ink
LINE_SHARE = 0.002  # door and window lines, as a share of the longer side


def render_png(
    shapes: Sequence[Shape],
    page_w: float,
    page_h: float,
    width: int,
    height: int,
    under: bytes | None = None,
) -> bytes:
    """The shapes (page pixels) drawn on a `width` x `height` image.

    Black on white, or in red over the photo `under` when one is given.
    """
    if under is None:
        image, ink = Image.new("RGB", (width, height), PAPER), INK
    else:
        with Image.open(io.BytesIO(under)) as photo:
            image, ink = photo.convert("RGB").resize((width, height)), OVER
    draw = ImageDraw.Draw(image)
    fx, fy = width / page_w, height / page_h
    line = max(1, round(LINE_SHARE * max(width, height)))

    def px(points: Sequence[Sequence[float]]) -> list[tuple[float, float]]:
        return [(p[0] * fx, p[1] * fy) for p in points]

    for s in shapes:
        props = s.properties
        if s.kind == "wall":
            for piece in props["pieces_px"]:
                draw.polygon(px(piece), fill=ink)
        elif s.kind == "door":
            draw.line(px(props["leaf_px"]), fill=ink, width=line)
            draw.line(px(props["arc_px"]), fill=ink, width=max(1, line // 2), joint="curve")
        elif s.kind == "window":
            for segment in props["lines_px"]:
                draw.line(px(segment), fill=ink, width=max(1, line // 2))
        elif s.kind in ("room", "text") and s.text:
            (x, y), size = px([props["label_px"]])[0], props["font_px"] * fy
            font = ImageFont.load_default(size=max(6.0, size))
            draw.text((x, y), s.text, fill=ink, font=font, anchor="mm")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def ink_box(photo_png: bytes) -> tuple[int, int, int, int] | None:
    """Where the photo's dark pixels are: (x0, y0, x1, y1), the far edges one past the ink.

    None when the photo has too little contrast, or when the dark reaches every edge
    (a shadow, a table): then the box says nothing about where the drawing is.
    """
    with Image.open(io.BytesIO(photo_png)) as photo:
        grey = photo.convert("L")
    low, high = grey.getextrema()
    if not isinstance(low, int) or not isinstance(high, int) or high - low < MIN_CONTRAST:
        return None
    middle = (low + high) / 2
    box = grey.point(lambda v: 255 if v < middle else 0).getbbox()
    if box is None or (box[0] == 0 and box[1] == 0 and box[2:] == grey.size):
        return None
    return box
