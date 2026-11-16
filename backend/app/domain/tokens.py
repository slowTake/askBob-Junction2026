"""Turn raw words (from PDF text or OCR) into drawing tokens and classify them."""

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.domain.dimensions import height_label, parse_area_m2, parse_dimension_mm, parse_scale
from app.domain.geometry import BBox, bbox_union
from app.domain.kinds import DrawingKind
from app.domain.vocab import (
    door_width_mm,
    is_fuzzy_room_name,
    lookup_code,
    lookup_room_name,
    room_code_number,
    unit_label,
)


@dataclass(frozen=True)
class Word:
    bbox: BBox
    text: str
    confidence: float = 1.0


@dataclass
class Classified:
    kind: DrawingKind
    label: str | None = None
    name: str | None = None
    value_mm: float | None = None
    properties: dict[str, Any] = field(default_factory=dict)


_DIGITS = re.compile(r"^\d{1,3}$")
_THOUSANDS = re.compile(r"^\d{3}$")
_ROOM_NUMBER = re.compile(r"^U?\d{1,2}\.\d{2}$")  # "2.01", "U1.05"
_WORD = re.compile(r"^[^\W\d_]{3,20}\.?$")  # one word of letters: "Slaapkamer", "Pukuh."


def merge_split_numbers(words: list[Word]) -> list[Word]:
    """Join "10" + "800" into "10 800" when the parts sit side by side on one line.

    Words must be in reading order. Two words merge when they overlap vertically by
    at least half the word height and the gap is under one word height.
    """
    out: list[Word] = []
    for word in words:
        prev = out[-1] if out else None
        if prev and _DIGITS.match(prev.text) and _THOUSANDS.match(word.text):
            height = prev.bbox[3] - prev.bbox[1]
            overlap = min(prev.bbox[3], word.bbox[3]) - max(prev.bbox[1], word.bbox[1])
            gap = word.bbox[0] - prev.bbox[2]
            if height > 0 and overlap >= height / 2 and 0 <= gap < height:
                out[-1] = Word(
                    bbox_union(prev.bbox, word.bbox),
                    f"{prev.text} {word.text}",
                    min(prev.confidence, word.confidence),
                )
                continue
        out.append(word)
    return out


def classify(text: str, fuzzy: bool = False) -> Classified:
    """Classify one token. Order matters: specific patterns before generic ones.

    `fuzzy` (OCR text) lets a room name match with one misread letter; the match is
    marked `fuzzy_match` so it can be flagged as doubtful.
    """
    scale = parse_scale(text)
    if scale is not None:
        return Classified("scale", label=text.strip(), properties={"denominator": scale})
    area = parse_area_m2(text)
    if area is not None:
        return Classified("area", label=text.strip(), properties={"area_m2": area})
    unit = unit_label(text)
    if unit is not None:
        return Classified("unit", label=unit, name=f"apartment {unit}")
    if _ROOM_NUMBER.match(text.strip()):
        return Classified("room_number", label=text.strip())
    height = height_label(text)
    if height is not None:
        return Classified("height", label=height, value_mm=int(height[1:]))
    room = lookup_room_name(text, fuzzy)
    if room is not None:
        category, outdoor = room
        local = " ".join(text.split())
        properties: dict[str, Any] = {
            "local_name": local,
            "category": category,
            "outdoor": outdoor,
        }
        if fuzzy and is_fuzzy_room_name(text):
            properties["fuzzy_match"] = True
        return Classified("room", label=local, name=f"{category} ({local})", properties=properties)
    code = lookup_code(text)
    if code is not None:
        numbered = room_code_number(text)
        number = numbered[1] if numbered else None
        label = f"{code.code}{number}" if number else code.code
        properties = {"local_name": code.local_name}
        if number:
            properties["code_number"] = number
        return Classified(
            code.kind, label=label, name=f"{code.english} ({label})", properties=properties
        )
    door = door_width_mm(text)
    if door is not None:
        return Classified("door", label=text.strip(), name=f"door {door} mm", value_mm=door)
    dimension = parse_dimension_mm(text)
    if dimension is not None:
        return Classified("dimension", label=text.strip(), value_mm=dimension)
    return Classified("text", label=text.strip())


def room_candidates(texts: Sequence[str]) -> set[str]:
    """Words the vocabulary doesn't know that a page prints at least twice, folded to
    lower case: likely room names in a language we have no list for (#36)."""
    words = [" ".join(t.split()) for t in texts]
    counts = Counter(w.lower() for w in words if _WORD.match(w) and classify(w).kind == "text")
    return {w for w, n in counts.items() if n >= 2}
