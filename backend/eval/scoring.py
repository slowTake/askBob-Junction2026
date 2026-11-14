"""Score an answer's value by question type, as the dataset scores it (D-013). Pure."""

from typing import Any

MEASURE_TOLERANCE = 0.02  # areas, lengths and volumes: within 2% of the expected value
MEASURES = frozenset({"area", "length", "volume"})


def score(question_type: str, expected: Any, value: float | None) -> bool | None:
    """True or False for counts and measures; None for types we do not score
    automatically (text, other). A missing value is wrong."""
    if question_type != "count" and question_type not in MEASURES:
        return None
    if value is None:
        return False
    if question_type == "count":
        return value == expected
    return abs(value - expected) <= MEASURE_TOLERANCE * abs(expected)
