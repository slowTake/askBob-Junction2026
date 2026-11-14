"""Upscale (#82): what a vision pass may add to a page, and when a page is done.

The model looks at a downscaled page image next to the elements ingest already
found and answers with what is missing. Nothing here calls the model: these
functions size the image, read its answer, and decide what is stored.

- Coordinates in the answer are pixels of the image as sent; `scale` maps them back.
- An entry that is malformed, unsure or off the page is skipped, never repaired.
- A candidate that overlaps an element of the same group is a duplicate. Ingest
  wins: its geometry is exact or already checked (D-014).
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.geometry import BBox, bbox_area

UPSCALE_SOURCE = "upscale"
UPSCALE_FORMAT = 1  # bump when the prompt or the merge rules change: pages run again

ADDABLE_KINDS = ("room", "door", "window", "wall")  # also the order they are listed in
MAX_CONFIDENCE = 0.9  # a vision result is never exact
MIN_CONFIDENCE = 0.3  # below this the model is guessing
DUPLICATE_OVERLAP = 0.5  # share of the smaller box
MIN_SIDE_PX = 2.0
MAX_ADDED = 200
MAX_LISTED = 150

_GROUPS = {"door": "opening", "window": "opening"}


@dataclass(frozen=True)
class Known:
    """An element ingest already stored, by where it is (see domain/extent.py)."""

    kind: str
    bbox: BBox
    label: str | None = None


@dataclass(frozen=True)
class Candidate:
    kind: str
    bbox: BBox  # page pixels
    label: str | None
    confidence: float


def image_scale(width_px: int, height_px: int, max_side: int) -> float:
    """Factor that fits the page's longest side into `max_side`; never enlarges."""
    if width_px <= 0 or height_px <= 0 or max_side <= 0:
        raise ValueError("a page and its image need a size")
    return min(1.0, max_side / max(width_px, height_px))


def overlap(a: BBox, b: BBox) -> float:
    """Shared area over the smaller box: 1.0 when one lies inside the other."""
    smaller = min(bbox_area(a), bbox_area(b))
    if smaller <= 0:
        return 0.0
    shared = bbox_area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))
    return shared / smaller


def parse_candidates(
    raw: object, scale: float, page_width: int, page_height: int
) -> list[Candidate]:
    """Read the model's answer. Raises ValueError when it has no element list at all."""
    entries = raw.get("elements") if isinstance(raw, Mapping) else None
    if not isinstance(entries, list):
        raise ValueError("the answer has no element list")
    found = (_candidate(entry, scale, page_width, page_height) for entry in entries)
    return [c for c in found if c is not None]


def merge_candidates(
    known: Sequence[Known], candidates: Sequence[Candidate], limit: int = MAX_ADDED
) -> list[Candidate]:
    """The candidates worth storing: surest first, no duplicates, at most `limit`."""
    taken = [(_group(k.kind), k.bbox) for k in known]
    added: list[Candidate] = []
    for candidate in sorted(candidates, key=lambda c: -c.confidence):  # stable
        if len(added) >= limit:
            break
        group = _group(candidate.kind)
        if any(g == group and overlap(candidate.bbox, b) >= DUPLICATE_OVERLAP for g, b in taken):
            continue
        taken.append((group, candidate.bbox))
        added.append(candidate)
    return added


def listed_elements(
    known: Sequence[Known], scale: float, limit: int = MAX_LISTED
) -> list[dict[str, object]]:
    """What the model is told is already known, in the sent image's pixels."""
    rows: list[dict[str, object]] = []
    for kind in ADDABLE_KINDS:
        for k in known:
            if k.kind != kind:
                continue
            row: dict[str, object] = {"kind": kind}
            if k.label:
                row["label"] = k.label
            row["box"] = [round(v * scale) for v in k.bbox]
            rows.append(row)
    return rows[:limit]


def cache_entry(
    document_version: int, model: str, added: int, input_tokens: int, output_tokens: int
) -> dict[str, object]:
    """What a page's meta keeps under "upscale" once the pass has run."""
    return {
        "document_version": document_version,
        "format": UPSCALE_FORMAT,
        "model": model,
        "added": added,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def is_cached(page_meta: Mapping[str, object], document_version: int) -> bool:
    """The pass already ran on this page, for this version of the document."""
    entry = page_meta.get("upscale")
    return (
        isinstance(entry, Mapping)
        and entry.get("document_version") == document_version
        and entry.get("format") == UPSCALE_FORMAT
    )


def _group(kind: str) -> str:
    return _GROUPS.get(kind, kind)


def _candidate(entry: object, scale: float, width: int, height: int) -> Candidate | None:
    if not isinstance(entry, Mapping) or entry.get("kind") not in ADDABLE_KINDS:
        return None
    numbers = [_number(entry.get(key)) for key in ("x0", "y0", "x1", "y1", "confidence")]
    if any(n is None for n in numbers):
        return None
    xa, ya, xb, yb, confidence = (n for n in numbers if n is not None)
    if confidence < MIN_CONFIDENCE:
        return None
    x0, x1 = sorted((_clamp(xa / scale, width), _clamp(xb / scale, width)))
    y0, y1 = sorted((_clamp(ya / scale, height), _clamp(yb / scale, height)))
    if x1 - x0 < MIN_SIDE_PX or y1 - y0 < MIN_SIDE_PX:
        return None
    raw_label = entry.get("label")
    label = raw_label.strip() if isinstance(raw_label, str) and raw_label.strip() else None
    kind = str(entry["kind"])
    if kind == "room" and label is None:
        return None  # an unnamed room says nothing a wall does not
    box = (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
    return Candidate(kind, box, label, min(confidence, MAX_CONFIDENCE))


def _clamp(value: float, limit: int) -> float:
    return max(0.0, min(value, float(limit)))


def _number(v: object) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)
