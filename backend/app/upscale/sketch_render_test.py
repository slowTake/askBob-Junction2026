"""The server-side render of a sketch draft: the shapes the frontend draws, as a PNG.

Page 1000 x 1000 px drawn at 500 x 500 (half size), so page point (x, y) lands on
pixel (x / 2, y / 2). Shapes come from sketch_shapes (outer wall 12 px thick).
"""

import io

from PIL import Image

from app.domain.sketch import Door, Plan, Room, Wall
from app.domain.sketch_drawing import sketch_shapes
from app.upscale.sketch_render import render_png

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
