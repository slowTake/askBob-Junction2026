"""The server-side render of a sketch draft: the shapes the frontend draws, as a PNG.

Page 1000 x 1000 px drawn at 500 x 500 (half size), so page point (x, y) lands on
pixel (x / 2, y / 2). Shapes come from sketch_shapes (outer wall 12 px thick).
"""

import io

from PIL import Image, ImageDraw

from app.domain.sketch import Door, Plan, Room, Wall
from app.domain.sketch_drawing import sketch_shapes
from app.upscale.sketch_render import ink_box, render_png

PLAN = Plan(
    walls=(Wall((100, 100), (500, 100), outer=True),),
    doors=(Door((200, 100), (260, 100), hinge_at_a=True, toward=(230, 150)),),
    rooms=(Room("bedroom", (300, 400), None),),
)


def _render() -> Image.Image:
    png = render_png(sketch_shapes(PLAN, 1000, 1000), 1000, 1000, 500, 500)
    return Image.open(io.BytesIO(png)).convert("L")


def _grey(image: Image.Image, xy: tuple[int, int]) -> int:
    value = image.getpixel(xy)
    assert isinstance(value, int)
    return value


def _darkest(image: Image.Image) -> int:
    low, _ = image.getextrema()
    assert isinstance(low, int)
    return low


def test_the_render_has_the_size_of_the_image_sent() -> None:
    assert _render().size == (500, 500)


def test_walls_are_filled_with_a_gap_at_the_door() -> None:
    image = _render()
    assert _grey(image, (150, 50)) < 64  # page (300, 100): inside the wall band
    assert _grey(image, (150, 40)) > 192  # page (300, 80): above the band, paper
    assert _grey(image, (115, 50)) > 192  # page (230, 100): the door's gap


def test_the_door_leaf_is_drawn_open() -> None:
    image = _render()
    # Leaf from hinge (200, 100) to (200, 160): pixel column 100, rows 50 to 80.
    assert _grey(image, (100, 65)) < 128


def test_room_names_are_written_at_their_point() -> None:
    image = _render()
    # "bedroom" at (300, 400), 24 px font: drawn around pixel (150, 200), 12 px high.
    box = image.crop((110, 190, 190, 210))
    assert _darkest(box) < 128  # some ink there
    assert _darkest(image.crop((0, 300, 500, 500))) > 192  # nothing else below


def _grey_photo() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (250, 250), (128, 128, 128)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_a_check_image_draws_the_draft_in_red_over_the_photo() -> None:
    # The photo (250 x 250) is stretched to the size sent (500 x 500) and kept under the draft.
    shapes = sketch_shapes(PLAN, 1000, 1000)
    png = render_png(shapes, 1000, 1000, 500, 500, under=_grey_photo())
    image = Image.open(io.BytesIO(png)).convert("RGB")
    assert image.size == (500, 500)
    assert image.getpixel((150, 40)) == (128, 128, 128)  # page (300, 80): photo, no draft
    pixel = image.getpixel((150, 50))  # page (300, 100): inside the wall band
    assert isinstance(pixel, tuple)
    red, green, blue = pixel[:3]
    assert red > 180 and green < 80 and blue < 80


def _photo_with_ink(box: tuple[int, int, int, int] | None) -> bytes:
    image = Image.new("RGB", (200, 100), (240, 240, 235))  # off-white paper
    if box:
        ImageDraw.Draw(image).rectangle(box, fill=(30, 30, 30))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_the_ink_box_is_where_the_dark_pixels_are() -> None:
    # Pillow's rectangle includes both corners: ink on columns 20..59 and rows 10..39,
    # so the box ends one past them, at (60, 40).
    assert ink_box(_photo_with_ink((20, 10, 59, 39))) == (20, 10, 60, 40)


def test_a_photo_without_ink_or_dark_all_over_has_no_ink_box() -> None:
    assert ink_box(_photo_with_ink(None)) is None
    # Ink to every edge (a shadow, a dark table): the box says nothing about the drawing.
    assert ink_box(_photo_with_ink((0, 0, 199, 99))) is None
