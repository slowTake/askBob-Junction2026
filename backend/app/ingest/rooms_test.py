import numpy as np

from app.ingest.rooms import ink_mask, room_region


def _closed_room() -> np.ndarray:
    """200x200 white page, room walls drawn with exact numpy slices (3 px thick).

    Ink rows 19..21 and 99..101, ink columns 19..21 and 119..121.
    """
    page = np.full((200, 200), 255, np.uint8)
    page[19:22, 19:122] = 0
    page[99:102, 19:122] = 0
    page[19:102, 19:22] = 0
    page[19:102, 119:122] = 0
    return page


def test_room_region_fills_interior() -> None:
    result = room_region(ink_mask(_closed_room()), seed=(70, 60), erase=[])
    assert result is not None
    polygon, area = result
    # Interior columns 22..118 (97 px) by rows 22..98 (77 px) = 7469 px, by hand.
    assert area == 97 * 77
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    assert (min(xs), min(ys), max(xs), max(ys)) == (22, 22, 118, 98)


def test_label_text_is_erased_from_barrier() -> None:
    page = _closed_room()
    page[55:66, 60:81] = 0  # a solid "label" covering the seed
    assert room_region(ink_mask(page), seed=(70, 60), erase=[]) is None
    assert room_region(ink_mask(page), seed=(70, 60), erase=[(60, 55, 80, 65)]) is not None


def test_leaking_room_is_rejected() -> None:
    page = _closed_room()
    page[19:22, 60:80] = 255  # 20 px gap in the top wall: the fill escapes to the whole page
    assert room_region(ink_mask(page), seed=(70, 60), erase=[], max_area_frac=0.25) is None


def test_fill_that_reaches_the_page_edge_is_rejected() -> None:
    page = _closed_room()
    page[19:22, 60:80] = 255  # gap in the top wall: the fill escapes to the page edge
    # Even with a generous area limit, touching the border means it leaked.
    assert room_region(ink_mask(page), seed=(70, 60), erase=[], max_area_frac=1.0) is None
