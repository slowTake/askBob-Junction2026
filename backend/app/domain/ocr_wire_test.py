from app.domain.ocr_wire import parse_words, words_to_json
from app.domain.tokens import Word


def test_words_round_trip() -> None:
    words = [Word((1.0, 2.0, 30.0, 12.0), "KITCHEN", 0.93), Word((0, 0, 5, 5), "3", 1.0)]
    assert parse_words({"words": words_to_json(words)}) == words


def test_json_shape() -> None:
    assert words_to_json([Word((1.5, 2, 3, 4), "WC", 0.5)]) == [
        {"bbox": [1.5, 2.0, 3.0, 4.0], "text": "WC", "confidence": 0.5}
    ]


def test_an_empty_page_is_a_valid_answer() -> None:
    assert parse_words({"words": []}) == []


def test_anything_malformed_is_rejected_whole() -> None:
    # None tells the caller to fall back to local OCR rather than trust half an answer.
    assert parse_words(None) is None
    assert parse_words({"nope": []}) is None
    assert parse_words({"words": "x"}) is None
    assert parse_words({"words": [{"bbox": [1, 2, 3], "text": "a", "confidence": 1}]}) is None
    assert parse_words({"words": [{"bbox": [1, 2, 3, "4"], "text": "a", "confidence": 1}]}) is None
    assert parse_words({"words": [{"bbox": [1, 2, 3, 4], "text": 5, "confidence": 1}]}) is None
    assert parse_words({"words": [{"bbox": [1, 2, 3, 4], "text": "a"}]}) is None
    assert parse_words({"words": [{"bbox": [1, 2, 3, 4], "text": "a", "confidence": True}]}) is None
