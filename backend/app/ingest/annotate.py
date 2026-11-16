"""Shared page pipeline for PDFs and images: words -> classified elements -> geometry."""

from collections import Counter
from typing import Any

from app.domain.areas import outline_agrees
from app.domain.dimensions import mm_per_px
from app.domain.geometry import (
    Point,
    bbox_center,
    footprint_mm,
    polygon_area,
)
from app.domain.kinds import DrawingKind
from app.domain.labels import (
    Label,
    is_numbering_scheme,
    link_room_labels,
    unnumbered_are_legend,
)
from app.domain.polygons import polygon_bbox
from app.domain.room_boundaries import holds_one_room
from app.domain.tokens import Word, classify, merge_split_numbers, room_candidates
from app.domain.vision import (
    Parsed,
    object_findings,
    wall_findings,
)
from app.ingest.dimension_lines import fit_dimension_scale
from app.ingest.line_trace import looks_like_text
from app.ingest.rooms import Gray, Mask, ink_mask, room_region
from app.ingest.traced_rooms import traced_outlines
from app.ingest.types import ExtractedElement
from app.ingest.vision_elements import to_element
from app.ingest.wall_trace import model_walls_beyond, trace_walls

WALL_CONFIDENCE = 0.3  # walls traced from pixels: the agent must verify visually
# The shortest wall run, as a share of the page's longest side: longer than the dashes
# and letters of colorful-34 (D-053).
MIN_RUN_SHARE = 0.04
MIN_RUN_PX = 12
VECTOR_WALL_CONFIDENCE = 0.95  # hatched regions from the PDF's vector layer
WALL: DrawingKind = "wall"


def annotate_page(
    gray: Gray,
    words: list[Word],
    source: str,
    dpi: float | None,
    vector_walls: list[list[Point]] | None = None,
    known_mm_per_px: float | None = None,
    vision: Parsed | None = None,
    vision_objects_only: bool = False,
) -> tuple[list[ExtractedElement], float | None, dict[str, Any]]:
    """Return the page's elements, its mm-per-pixel scale (if known) and page metadata.

    `vector_walls` are exact wall outlines in page pixels (from a PDF's vector
    layer); when given, they are the page's walls. Otherwise walls are traced from the
    ink (D-053).
    `known_mm_per_px` is an exact scale (e.g. a rendered CAD drawing), which wins
    over a printed scale note.
    `vision` is the floor-plan model's reading of the page (D-022). It always adds
    doors, windows and fixtures; unless `vision_objects_only`, its walls join the traced
    ones, and the ink's outline wins where both have a wall. Room highlights always use
    the drawing's traced boundaries; segmentation fragments are not room boundaries.
    """
    words = merge_split_numbers(words)
    elements: list[ExtractedElement] = []
    scales: list[int] = []
    repeated = room_candidates([w.text for w in words])
    for word in words:
        c = classify(word.text, fuzzy=source == "ocr")  # one misread letter in a name
        if c.kind == "text" and " ".join(word.text.split()).lower() in repeated:
            c.properties["room_candidate"] = True  # kept as text: not traced as a room
        if c.kind == "scale":
            scales.append(int(c.properties["denominator"]))
        elements.append(
            ExtractedElement(
                kind=c.kind,
                source=source,
                text=word.text,
                label=c.label,
                name=c.name,
                value_mm=c.value_mm,
                bbox=word.bbox,
                properties=c.properties,
                confidence=word.confidence,
            )
        )

    _link_printed_labels(elements)

    height = float(gray.shape[0])
    ink = ink_mask(gray)
    text_boxes = [w.bbox for w in words]

    scale_mm: float | None = None
    scale_meta: dict[str, Any] = {"scale_method": None}
    if known_mm_per_px:  # a CAD file's exact scale
        scale_mm = known_mm_per_px
        scale_meta["scale_method"] = "cad"
    elif dpi and scales:
        scale_mm = mm_per_px(dpi, scales[0])
        scale_meta["scale_method"] = "dpi"
    else:  # no DPI or no scale note: fit the printed dimensions to their dimension lines
        dimensions = [
            (el.value_mm, el.bbox)
            for el in elements
            if el.kind == "dimension" and el.value_mm and el.bbox
        ]
        fit = fit_dimension_scale(ink, dimensions, erase=text_boxes)
        if fit:
            scale_mm, support = fit
            scale_meta = {"scale_method": "dimension_fit", "scale_support": support}
    # TODO(scale): scale bars (HABS, Finna) as a third method, "scale_bar".

    model_rooms = vision is not None and not vision_objects_only
    rooms = [el for el in elements if el.kind == "room" and el.bbox is not None]
    label_points = [bbox_center(el.bbox) for el in rooms if el.bbox is not None]
    # Room numbers not linked to a name still mark a room: counting them stops a region
    # that holds two rooms' labels from being given to one of them (D-024).
    linked = {el.properties.get("number") for el in rooms}
    other_rooms = [
        bbox_center(el.bbox)
        for el in elements
        if el.kind == "room_number" and el.bbox is not None and el.label not in linked
    ]
    traced = traced_outlines(gray, words, label_points + other_rooms, dpi)[: len(rooms)]
    sources: Counter[str] = Counter()
    for index, (el, centre, from_lines) in enumerate(zip(rooms, label_points, traced, strict=True)):
        # Only a boundary traced from the drawing can outline a printed room.
        # Model masks can cover an apartment or just a patch of a corridor; flood
        # fills can run through doors. Neither is evidence of this room's extent.
        candidates: list[tuple[str, list[Point] | None]] = [("traced", from_lines)]
        if known_mm_per_px and from_lines is None:
            # A CAD rendering has an exact scale and closed native geometry.
            # Keep its existing region fallback, with the same label checks.
            filled = room_region(ink, centre, erase=text_boxes, close_px=3, max_area_frac=1.0)
            candidates.append(("cad_region", filled[0] if filled else None))
        neighbours = label_points[:index] + label_points[index + 1 :] + other_rooms
        safe: list[tuple[str, list[Point] | None]] = [
            (origin, polygon)
            for origin, polygon in candidates
            if polygon and holds_one_room(polygon, centre, neighbours)
        ]
        chosen = _first_agreeing(safe, el.properties.get("printed_area_m2"), scale_mm)
        if chosen is None:
            closed = any(polygon for _, polygon in candidates)
            el.properties["region"] = (
                "multiple_room_labels"
                if closed and not safe
                else "disagrees_with_printed_area"
                if closed
                else "not_closed"
            )
            continue
        source, polygon = chosen
        sources[source] += 1
        el.properties["polygon_px"] = [list(p) for p in polygon]
        el.properties["outline_source"] = source
        if scale_mm:
            measured = round(polygon_area(polygon) * scale_mm * scale_mm / 1e6, 2)
            el.properties["measured_area_m2"] = measured
            el.properties.setdefault("area_m2", measured)
            el.footprint_mm = footprint_mm(polygon, scale_mm, height)

    if vector_walls:
        for outline in vector_walls:
            wall = ExtractedElement(
                kind=WALL, source="pdf_vector", bbox=polygon_bbox(outline),
                confidence=VECTOR_WALL_CONFIDENCE,
                properties={"polygon_px": [list(p) for p in outline]},
            )  # fmt: skip
            if scale_mm:
                wall.footprint_mm = footprint_mm(outline, scale_mm, height)
            elements.append(wall)
    else:
        elements += _traced_walls(ink, words, elements, vision if model_rooms else None,
                                  scale_mm, height)  # fmt: skip

    if vision is not None:
        elements += [to_element(o, scale_mm, height) for o in object_findings(vision)]

    meta = {
        "scale_denominators": scales,
        "scale_known": scale_mm is not None,
        **scale_meta,
        "words": len(words),
        "room_outlines": dict(sources),
    }
    return elements, scale_mm, meta


def _traced_walls(
    ink: Mask,
    words: list[Word],
    elements: list[ExtractedElement],
    vision: Parsed | None,
    scale_mm: float | None,
    height: float,
) -> list[ExtractedElement]:
    """Walls traced from the ink (D-053), and the model's walls the trace did not find."""
    min_run = max(MIN_RUN_PX, round(MIN_RUN_SHARE * max(ink.shape)))
    text = [w.bbox for w in words if looks_like_text(w.text)]
    dimensions = [e.bbox for e in elements if e.kind == "dimension" and e.bbox is not None]
    traced = trace_walls(ink, min_run, text_boxes=text, dimension_boxes=dimensions)
    walls = []
    for t in traced:
        wall = ExtractedElement(
            kind=WALL, source="derived", bbox=polygon_bbox(t.polygon), confidence=WALL_CONFIDENCE,
            properties={"polygon_px": [list(p) for p in t.polygon],
                        "thickness_px": t.thickness_px, "drawn": t.drawn},
        )  # fmt: skip
        if scale_mm:
            wall.footprint_mm = footprint_mm(t.polygon, scale_mm, height)
        walls.append(wall)
    if vision is not None:
        model = wall_findings(vision)
        beyond = model_walls_beyond(traced, [f.polygon for f in model], ink.shape)
        walls += [to_element(f, scale_mm, height) for f in model if f.polygon in beyond]
    return walls


def _first_agreeing(
    candidates: list[tuple[str, list[Point] | None]],
    printed_m2: float | None,
    scale_mm: float | None,
) -> tuple[str, list[Point]] | None:
    """The first outline whose area matches the printed one (any, if none is printed
    or the scale is unknown)."""
    for source, polygon in candidates:
        if not polygon:
            continue
        if scale_mm is None:
            return source, polygon
        measured = polygon_area(polygon) * scale_mm * scale_mm / 1e6
        if outline_agrees(measured, printed_m2):
            return source, polygon
    return None


def _link_printed_labels(elements: list[ExtractedElement]) -> None:
    """Give each room its printed number and area ("Zimmer / 2.01 / 15.61 m²").

    A printed area is exact (it comes from the architect's model), so it wins over
    any area we measure from pixels.
    """
    labels = [Label(e.kind, e.bbox) for e in elements if e.bbox is not None]
    indexed = [e for e in elements if e.bbox is not None]
    links = link_room_labels(labels)
    numbers = [indexed[f["room_number"]].label or "" for f in links.values() if "room_number" in f]
    if len(numbers) >= 3 and not is_numbering_scheme(numbers):
        # "d.dd" under a name can be a metre dimension ("3.20"), not a room number:
        # without a plan-wide numbering, link no numbers and keep every room a room.
        # (Fewer than three can't switch rooms to legend entries, so they stay linked.)
        for found in links.values():
            found.pop("room_number", None)
    rooms = [i for i, lb in enumerate(labels) if lb.kind == "room"]
    numbered = sum(1 for i in rooms if "room_number" in links.get(i, {}))
    if unnumbered_are_legend(numbered, len(rooms) - numbered):
        for i in rooms:
            if "room_number" not in links.get(i, {}):
                indexed[i].kind = "text"  # a legend entry, e.g. "WC" in the key box
                indexed[i].properties["legend"] = True
    for room_i, found in links.items():
        room = indexed[room_i]
        if "room_number" in found:
            number = indexed[found["room_number"]].label
            room.properties["number"] = number
            room.name = f"{room.name} {number}"
        if "area" in found:
            area = indexed[found["area"]].properties["area_m2"]
            room.properties["printed_area_m2"] = area
            room.properties["area_m2"] = area
