"""OCR words as JSON, between the worker and the OCR service (#119). Pure."""

from typing import Any

from app.domain.tokens import Word


def words_to_json(words: list[Word]) -> list[dict[str, Any]]:
    return [
        {"bbox": [float(v) for v in w.bbox], "text": w.text, "confidence": float(w.confidence)}
        for w in words
    ]


def _number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def parse_words(data: Any) -> list[Word] | None:
    """The words in a service answer, or None if any part is malformed (never half)."""
    if not isinstance(data, dict) or not isinstance(data.get("words"), list):
        return None
    words: list[Word] = []
    for item in data["words"]:
        if not isinstance(item, dict):
            return None
        bbox, text, confidence = item.get("bbox"), item.get("text"), item.get("confidence")
        if not (isinstance(bbox, list) and len(bbox) == 4 and all(_number(v) for v in bbox)):
            return None
        if not isinstance(text, str) or not isinstance(confidence, int | float):
            return None
        if isinstance(confidence, bool):
            return None
        x0, y0, x1, y1 = (float(v) for v in bbox)
        words.append(Word((x0, y0, x1, y1), text, float(confidence)))
    return words
