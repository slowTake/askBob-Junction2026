"""Score an answer against an expected value. Pure; used by run_eval.py."""

import re

_NUMBER = re.compile(r"\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?")


def numbers_in(text: str) -> list[float]:
    """ "The door is 900 mm, the room 10 800 mm and 12,5 m²" -> [900, 10800, 12.5]."""
    return [float(m.replace(" ", "").replace("\u00a0", "").replace(",", ".")) for m in
            _NUMBER.findall(text)]  # fmt: skip


def is_correct(expected: str, answer: str, rel_tolerance: float = 0.02) -> bool:
    """Numeric expectations match any number in the answer within the tolerance;
    text expectations must appear in the answer (case-insensitive)."""
    expected_numbers = numbers_in(expected)
    if expected_numbers and _NUMBER.fullmatch(expected.strip()):
        target = expected_numbers[0]
        return any(abs(n - target) <= rel_tolerance * abs(target) for n in numbers_in(answer))
    return expected.strip().lower() in answer.lower()
