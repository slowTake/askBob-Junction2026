"""What a CAD layer holds, from its name, and DXF drawing units."""

# Checked in order: the first matching keyword wins ("ROOM_TEXT" is text, not a room).
_ROLES: list[tuple[str, tuple[str, ...]]] = [
    ("text", ("text", "annotation", "anno", "beschrift", "texte", "testo")),
    ("unit", ("unit", "apartment", "wohnung", "whg", "appartement", "logement", "alloggio")),
    ("room", ("room", "space", "raum", "piece", "pièce", "locale", "stanza", "area")),
    ("wall", ("wall", "wand", "mauer", "mur", "muro", "parete")),
    ("door", ("door", "tür", "tuer", "porte", "porta")),
    ("window", ("window", "fenster", "fenêtre", "fenetre", "finestra")),
    ("fixture", ("fixture", "sanit", "furniture", "möbel", "mobil", "equipment")),
]

# DXF $INSUNITS codes -> millimetres per drawing unit.
_UNITS_MM = {1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0, 14: 100.0}


def layer_role(layer: str) -> str | None:
    name = layer.lower()
    for role, keywords in _ROLES:
        if any(k in name for k in keywords):
            return role
    return None


def units_to_mm(insunits: int | None) -> float | None:
    """None when the file doesn't say (0 = unitless); the caller must guess."""
    return _UNITS_MM.get(insunits or 0)
