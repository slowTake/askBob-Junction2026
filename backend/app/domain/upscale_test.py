"""The pure part of Upscale (#82): scale, parse, merge and the cache entry.

Every expected value is worked out by hand in the comment next to it.
"""

import pytest

from app.domain.upscale import (
    MAX_CONFIDENCE,
    UPSCALE_FORMAT,
    Candidate,
    Known,
    cache_entry,
    image_scale,
    is_cached,
    listed_elements,
    merge_candidates,
    overlap,
    parse_candidates,
)


def _raw(kind: str = "door", box: tuple[object, ...] = (10, 10, 30, 30), **over: object) -> dict:
    x0, y0, x1, y1 = box
    return {
        "kind": kind, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "label": None, "confidence": 0.8,
        **over,
    }  # fmt: skip


class TestImageScale:
    def test_shrinks_the_longest_side_to_the_limit(self) -> None:
        assert image_scale(3000, 2000, 1500) == 0.5  # 1500 / 3000
        assert image_scale(1000, 4000, 1000) == 0.25  # 1000 / 4000, the height is longest

    def test_never_enlarges_a_small_page(self) -> None:
        assert image_scale(800, 600, 1568) == 1.0

    def test_an_empty_page_has_no_scale(self) -> None:
        with pytest.raises(ValueError):
            image_scale(0, 600, 1568)


class TestOverlap:
    def test_is_the_shared_area_over_the_smaller_box(self) -> None:
        # Shared 5 x 10 = 50; both boxes are 10 x 10 = 100, so 50 / 100.
        assert overlap((0, 0, 10, 10), (5, 0, 15, 10)) == 0.5

    def test_a_box_inside_another_overlaps_fully(self) -> None:
        # The 10 x 10 label lies inside the 100 x 100 room: 100 / 100.
        assert overlap((0, 0, 100, 100), (20, 20, 30, 30)) == 1.0

    def test_apart_or_empty_boxes_do_not_overlap(self) -> None:
        assert overlap((0, 0, 10, 10), (20, 0, 30, 10)) == 0.0
        assert overlap((0, 0, 10, 10), (5, 5, 5, 9)) == 0.0  # zero width


class TestParseCandidates:
    def test_maps_image_pixels_back_to_page_pixels(self) -> None:
        raw = {"elements": [_raw("wall", (100, 50, 200, 60), confidence=0.7)]}
        # The image was sent at half size, so every coordinate doubles.
        assert parse_candidates(raw, 0.5, 1000, 800) == [
            Candidate("wall", (200.0, 100.0, 400.0, 120.0), None, 0.7)
        ]

    def test_clamps_a_box_to_the_page(self) -> None:
        raw = {"elements": [_raw("window", (450, 390, 520, 410))]}
        # Doubled: (900, 780, 1040, 820); the page ends at 1000 x 800.
        [found] = parse_candidates(raw, 0.5, 1000, 800)
        assert found.bbox == (900.0, 780.0, 1000.0, 800.0)

    def test_orders_reversed_corners(self) -> None:
        [found] = parse_candidates({"elements": [_raw(box=(30, 30, 10, 10))]}, 1.0, 100, 100)
        assert found.bbox == (10.0, 10.0, 30.0, 30.0)

    def test_confidence_stays_below_one(self) -> None:
        raw = {"elements": [_raw(confidence=0.95), _raw(confidence=1)]}
        found = parse_candidates(raw, 1.0, 100, 100)
        assert MAX_CONFIDENCE == 0.9
        assert [c.confidence for c in found] == [0.9, 0.9]

    def test_drops_what_the_model_is_unsure_of(self) -> None:
        raw = {"elements": [_raw(confidence=0.29), _raw(confidence=0.3)]}
        assert [c.confidence for c in parse_candidates(raw, 1.0, 100, 100)] == [0.3]

    def test_keeps_a_trimmed_label_and_requires_one_for_rooms(self) -> None:
        raw = {
            "elements": [
                _raw("room", (0, 0, 50, 50), label="  Küche "),
                _raw("room", (50, 0, 100, 50), label=None),
                _raw("room", (50, 50, 100, 100), label="   "),
                _raw("door", label="09"),
            ]
        }
        found = parse_candidates(raw, 1.0, 100, 100)
        assert [(c.kind, c.label) for c in found] == [("room", "Küche"), ("door", "09")]

    @pytest.mark.parametrize(
        "entry",
        [
            _raw("stair"),  # not a kind Upscale adds
            _raw(box=(10, 10, "30", 30)),  # a coordinate that is not a number
            _raw(box=(10, 10, float("nan"), 30)),
            _raw(box=(10, 10, True, 30)),  # booleans are not coordinates
            _raw(confidence="high"),
            _raw(box=(10, 10, 11, 30)),  # 1 px wide: under the 2 px minimum
            _raw(box=(120, 10, 150, 30)),  # right of the 100 px page: empty after clamping
            {"kind": "door"},  # no box at all
            "door",
            None,
        ],
    )
    def test_skips_a_malformed_entry_and_keeps_the_rest(self, entry: object) -> None:
        raw = {"elements": [entry, _raw("wall", (0, 0, 50, 4))]}
        assert [c.kind for c in parse_candidates(raw, 1.0, 100, 100)] == ["wall"]

    @pytest.mark.parametrize("raw", [None, [], {"items": []}, {"elements": "none"}])
    def test_rejects_an_answer_without_an_element_list(self, raw: object) -> None:
        with pytest.raises(ValueError):
            parse_candidates(raw, 1.0, 100, 100)

    def test_an_empty_list_is_a_valid_answer(self) -> None:
        assert parse_candidates({"elements": []}, 1.0, 100, 100) == []


class TestMergeCandidates:
    def test_drops_a_candidate_that_covers_an_existing_element(self) -> None:
        known = [Known("door", (100, 100, 140, 140))]
        # Shared 30 x 40 = 1200 of 1600: 0.75, a duplicate.
        again = Candidate("door", (110, 100, 150, 140), None, 0.8)
        # Shared 10 x 40 = 400 of 1600: 0.25, a neighbour.
        beside = Candidate("door", (130, 100, 170, 140), None, 0.8)
        assert merge_candidates(known, [again, beside]) == [beside]

    def test_doors_and_windows_are_one_group(self) -> None:
        # The model may call an extracted window a door: still the same opening.
        known = [Known("window", (100, 100, 140, 140))]
        assert merge_candidates(known, [Candidate("door", (100, 100, 140, 140), None, 0.8)]) == []

    def test_a_wall_under_a_door_is_not_a_duplicate(self) -> None:
        known = [Known("door", (100, 100, 140, 140))]
        wall = Candidate("wall", (100, 100, 140, 140), None, 0.8)
        assert merge_candidates(known, [wall]) == [wall]

    def test_a_room_whose_name_is_already_known_is_dropped(self) -> None:
        # The extracted room is only its printed name (a 40 x 20 box) inside the outline.
        known = [Known("room", (200, 200, 240, 220))]
        assert merge_candidates(known, [Candidate("room", (100, 100, 400, 300), "MH", 0.8)]) == []

    def test_keeps_the_surer_of_two_candidates_for_the_same_spot(self) -> None:
        weak = Candidate("wall", (0, 0, 100, 10), None, 0.5)
        sure = Candidate("wall", (0, 0, 100, 12), None, 0.8)
        other = Candidate("wall", (0, 50, 100, 60), None, 0.4)
        # Surest first; the weak one overlaps the sure one fully (1000 / 1000).
        assert merge_candidates([], [weak, sure, other]) == [sure, other]

    def test_caps_how_many_are_added(self) -> None:
        # Ten walls stacked 20 px apart never overlap; the cap keeps the first three.
        walls = [Candidate("wall", (0, 20 * i, 100, 20 * i + 5), None, 0.8) for i in range(10)]
        assert merge_candidates([], walls, limit=3) == walls[:3]


class TestListedElements:
    def test_lists_known_elements_in_the_sent_image_s_pixels(self) -> None:
        known = [Known("wall", (200, 100, 400, 120)), Known("room", (10, 20, 32, 44), "MH")]
        # Halved; rooms come first: (10, 20, 32, 44) / 2 = (5, 10, 16, 22).
        assert listed_elements(known, 0.5, limit=10) == [
            {"kind": "room", "label": "MH", "box": [5, 10, 16, 22]},
            {"kind": "wall", "box": [100, 50, 200, 60]},
        ]

    def test_leaves_out_kinds_upscale_never_adds_and_stops_at_the_limit(self) -> None:
        known = [
            Known("text", (0, 0, 10, 10), "NOTE"),
            Known("door", (0, 0, 10, 10)),
            Known("door", (20, 0, 30, 10)),
        ]
        assert listed_elements(known, 1.0, limit=1) == [{"kind": "door", "box": [0, 0, 10, 10]}]


class TestCache:
    def test_a_page_is_cached_for_the_document_version_it_was_upscaled_at(self) -> None:
        meta = {"storey": "L1", "upscale": cache_entry(3, "some-model", 4, 1200, 300)}
        assert meta["upscale"] == {
            "document_version": 3,
            "format": UPSCALE_FORMAT,
            "model": "some-model",
            "added": 4,
            "input_tokens": 1200,
            "output_tokens": 300,
        }
        assert is_cached(meta, 3) is True
        assert is_cached(meta, 4) is False  # re-ingested since

    def test_a_page_never_upscaled_or_upscaled_in_an_old_format_is_not_cached(self) -> None:
        assert is_cached({}, 1) is False
        assert is_cached({"upscale": "yes"}, 1) is False
        old = {**cache_entry(1, "m", 0, 0, 0), "format": UPSCALE_FORMAT - 1}
        assert is_cached({"upscale": old}, 1) is False
