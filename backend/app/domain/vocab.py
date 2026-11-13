"""Drawing vocabulary for Nordic (Finnish and Swedish) architectural plans.

Codes are the abbreviations printed inside rooms and next to fixtures, e.g.
"MH" = makuuhuone (bedroom). Extend these tables as the dataset shows new codes.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Code:
    code: str
    kind: str  # "room" or "fixture"
    local_name: str
    english: str


_ROOMS = [
    ("MH", "makuuhuone", "bedroom"),
    ("OH", "olohuone", "living room"),
    ("K", "keittiö", "kitchen"),
    ("KK", "keittokomero", "kitchenette"),
    ("RT", "ruokailutila", "dining area"),
    ("KH", "kylpyhuone", "bathroom"),
    ("PH", "pesuhuone", "washroom"),
    ("S", "sauna", "sauna"),
    ("SAU", "sauna", "sauna"),
    ("WC", "wc", "toilet"),
    ("ET", "eteinen", "hall"),
    ("VH", "vaatehuone", "walk-in closet"),
    ("KHH", "kodinhoitohuone", "utility room"),
    ("VAR", "varasto", "storage"),
    ("AH", "askarteluhuone", "hobby room"),
    ("TK", "tekninen tila", "technical room"),
    ("PARV", "parveke", "balcony"),
    ("TERA", "terassi", "terrace"),
    ("SOV", "sovrum", "bedroom"),
    ("VARD", "vardagsrum", "living room"),
    ("KÖK", "kök", "kitchen"),
    ("BAD", "badrum", "bathroom"),
    ("HALL", "hall", "hall"),
    ("FÖRR", "förråd", "storage"),
]

_FIXTURES = [
    ("JK", "jääkaappi", "fridge"),
    ("PK", "pakastin", "freezer"),
    ("JK-KK", "jääkaappi-kylmäkaappi", "fridge column"),
    ("PK-V", "pakastin", "freezer"),
    ("APK", "astianpesukone", "dishwasher"),
    ("APK-V", "astianpesukone", "dishwasher"),
    ("SK", "siivouskaappi", "cleaning cupboard"),
    ("LVK", "lämminvesivaraaja", "water heater"),
    ("PYK", "pyykinpesukone", "washing machine"),
    ("KUI", "kuivausrumpu", "tumble dryer"),
]

CODES: dict[str, Code] = {
    **{c: Code(c, "room", local, en) for c, local, en in _ROOMS},
    **{c: Code(c, "fixture", local, en) for c, local, en in _FIXTURES},
}

_DOOR_TAG = re.compile(r"^(0[6-9]|1[0-2])$")


def lookup_code(text: str) -> Code | None:
    """Look up a room or fixture code; tolerates case, spaces and trailing dots."""
    key = text.strip().rstrip(".").upper().replace(" ", "")
    return CODES.get(key)


def door_width_mm(text: str) -> int | None:
    """Door tags give the leaf width in modules of 100 mm: "09" is a 900 mm door.

    Only zero-padded 06-09 and 10-12 count, so grid labels like "3" are ignored.
    """
    match = _DOOR_TAG.match(text.strip())
    return int(match.group(1)) * 100 if match else None
