"""Every element kind the drawing pipeline (PDFs and images) can store.

The IFC kinds are in app/domain/ifc_mapping.py (IFC_KINDS). Type a new drawing kind
here first: tokens.py, vocab.py and annotate.py use these types, so mypy rejects a
kind that is missing, and the agent's find_elements filter is tested against
DRAWING_KINDS (app/qa/tools_test.py).
"""

from typing import Literal, get_args

CodeKind = Literal["room", "fixture"]  # what a vocabulary code names
DrawingKind = Literal[
    CodeKind,
    "room_number",
    "unit",
    "door",
    "window",
    "dimension",
    "height",  # a printed ceiling height, "h1600" (value_mm)
    "scale",
    "area",
    "text",
    "wall",
]

DRAWING_KINDS: frozenset[str] = frozenset(get_args(DrawingKind))
