"""Drawing vocabulary for Nordic (Finnish and Swedish) architectural plans.

Codes are the abbreviations printed inside rooms and next to fixtures, e.g.
"MH" = makuuhuone (bedroom). Extend these tables as the dataset shows new codes.
"""

import re
import unicodedata
from dataclasses import dataclass

from app.domain.kinds import CodeKind


@dataclass(frozen=True)
class Code:
    code: str
    kind: CodeKind
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


def _fold(text: str) -> str:
    """Lower case, single spaces, accents removed: "Séjour/repas" -> "sejour/repas"."""
    decomposed = unicodedata.normalize("NFKD", " ".join(text.split()).lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


# Full room names as printed (German, French, Italian, English) -> (category, outdoor).
# Collected from the ROOM_TEXT layer of the dataset's swiss_dwellings DXFs.
_ROOM_NAMES: dict[str, tuple[str, bool]] = {}
for _category, _outdoor, _names in [
    ("room", False, "Zimmer|Pièce|Stanza|Locale|Room"),
    ("bedroom", False, "Schlafzimmer|Chambre à coucher|Camera da letto|Bedroom"),
    (
        "living room",
        False,
        "Wohnen/Essen|Wohnen|Séjour/repas|Séjour|Soggiorno/pranzo|Soggiorno|Living room",
    ),
    ("dining", False, "Essen|Repas|Pranzo|Dining"),
    ("kitchen", False, "Küche|Cuisine|Cucina|Kitchen"),
    ("bathroom", False, "Bad|Bain|Bagno|Dusche|Douche|Doccia|Bathroom|Shower"),
    ("toilet", False, "WC|Toilet"),
    ("corridor", False, "Korridor|Gang|Couloir|Corridoio|Corridor|Hall|Entrée|Ingresso"),
    ("storage", False, "Reduit|Réduit|Ripostiglio|Abstellraum|Storage"),
    ("stairwell", False, "Treppenhaus|Cage d'escalier|Vano scala|Stairwell"),
    ("elevator", False, "Lift|Aufzug|Ascenseur|Ascensore|Elevator"),
    ("entrance hall", False, "Eingangshalle|Hall d'entrée"),
    ("office", False, "Bürofläche|Büro|Bureau|Ufficio|Office"),
    ("balcony", True, "Balkon|Balcon|Balcone|Balcony"),
    ("loggia", True, "Loggia"),
    ("terrace", True, "Terrasse|Terrazza|Terrace"),
]:
    for _name in _names.split("|"):
        _ROOM_NAMES[_fold(_name)] = (_category, _outdoor)

_UNIT = re.compile(
    r"^(?:App\.?|Apt\.?|Whg\.?|Apartment|Appartement|Wohnung|Appartamento)\s+([A-Z0-9]{1,3})$",
    re.IGNORECASE,
)


def lookup_room_name(text: str) -> tuple[str, bool] | None:
    """A printed room name -> (category, is_outdoor). Exact match, ignoring case,
    spacing and accents (an OCR without accented letters reads "Pièce" as "Piece")."""
    return _ROOM_NAMES.get(_fold(text))


def unit_label(text: str) -> str | None:
    """ "App. A" / "Whg. B" / "Apartment 12" -> the unit's id."""
    match = _UNIT.match(" ".join(text.split()))
    return match.group(1).upper() if match else None


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
