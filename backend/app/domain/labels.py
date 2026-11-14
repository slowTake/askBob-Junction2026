"""Link a room's name to the number and area printed under it ("Zimmer / 2.01 / 15.61 m²")."""

from dataclasses import dataclass

from app.domain.geometry import BBox, bbox_center

MAX_LINES_BELOW = 4.0  # how far down to look, in text heights


@dataclass(frozen=True)
class Label:
    kind: str  # room | room_number | area | ...
    bbox: BBox


def link_room_labels(labels: list[Label]) -> dict[int, dict[str, int]]:
    """For each room label index, the index of its `room_number` and `area` labels.

    A match sits below the name, within a few text heights, and horizontally
    overlaps it. Nearest first; each number or area is used at most once.
    """
    used: set[int] = set()
    links: dict[int, dict[str, int]] = {}
    rooms = sorted((i for i, lb in enumerate(labels) if lb.kind == "room"),
                   key=lambda i: labels[i].bbox[1])  # fmt: skip
    for r in rooms:
        x0, y0, x1, y1 = labels[r].bbox
        height = max(y1 - y0, 1e-6)
        found: dict[str, int] = {}
        for kind in ("room_number", "area"):
            best: tuple[float, int] | None = None
            for i, lb in enumerate(labels):
                if lb.kind != kind or i in used:
                    continue
                cx, _ = bbox_center(lb.bbox)
                below = lb.bbox[1] - y1
                if not (x0 - height <= cx <= x1 + height) or below < -0.25 * height:
                    continue
                if below > MAX_LINES_BELOW * height:
                    continue
                if best is None or below < best[0]:
                    best = (below, i)
            if best is not None:
                found[kind] = best[1]
                used.add(best[1])
        if found:
            links[r] = found
    return links


def unnumbered_are_legend(numbered: int, unnumbered: int) -> bool:
    """On a plan that numbers its rooms, a room name without a number is a legend
    entry, not a room. Needs a few numbered rooms to be sure of the convention."""
    return numbered >= 3 and numbered > unnumbered
