"""Parse dimension strings, scale notes and areas printed on drawings."""

import re

_DIMENSION = re.compile(r"^(\d{1,3})[ \u00a0\u202f](\d{3})$|^(\d{2,6})$")
_SCALE = re.compile(r"^1\s*:\s*(\d{1,4})$")
_AREA = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(?:M2|M²|m2|m²)$")

MM_PER_INCH = 25.4
MIN_DIMENSION_MM = 50
MAX_DIMENSION_MM = 200_000


def parse_dimension_mm(text: str) -> int | None:
    """Nordic drawings write dimensions in millimetres, thousands split by a space.

    "10 800" -> 10800, "3600" -> 3600. Values outside 50 mm to 200 m are rejected
    because they are almost always grid labels, codes or page numbers.
    """
    match = _DIMENSION.match(text.strip())
    if not match:
        return None
    value = int(match.group(1) + match.group(2)) if match.group(1) else int(match.group(3))
    if text.strip().startswith("0"):
        return None
    return value if MIN_DIMENSION_MM <= value <= MAX_DIMENSION_MM else None


def parse_scale(text: str) -> int | None:
    """ "1:50" -> 50. Returns the scale denominator."""
    match = _SCALE.match(text.strip())
    if not match:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


def parse_area_m2(text: str) -> float | None:
    """ "80M2", "80 m²", "12,5 m2" -> area in square metres."""
    match = _AREA.match(text.strip())
    return float(match.group(1).replace(",", ".")) if match else None


def mm_per_px(dpi: float, scale_denominator: int) -> float:
    """Real-world millimetres per rendered pixel for a page drawn at 1:scale."""
    return MM_PER_INCH / dpi * scale_denominator
