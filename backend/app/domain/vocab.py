"""Drawing vocabulary: Nordic room and fixture codes, and room names written out.

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
    ("KPH", "kylpyhuone", "bathroom"),
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

# Finnish room names written out (colorful-34 in eval/redraw_bench, CubiCasa questions),
# with the abbreviations printed on the plans. Only these are matched fuzzily (D-050).
_FINNISH_NAMES: dict[str, tuple[str, bool]] = {}
for _category, _outdoor, _names in [
    ("kitchen", False, "keittiö"),
    ("kitchenette", False, "keittokomero"),
    ("dining", False, "ruokailutila"),
    ("corridor", False, "aula|käytävä"),
    ("entrance hall", False, "eteinen"),
    ("office", False, "työhuone|työh.|työh"),
    ("porch", True, "kuisti"),
    ("walk-in closet", False, "vaatehuone"),
    ("storage", False, "varasto"),
    ("dressing room", False, "pukuhuone|pukuh.|pukuh"),
    ("bedroom", False, "makuuhuone"),
    ("living room", False, "olohuone"),
    ("bathroom", False, "kylpyhuone"),
    ("washroom", False, "pesuhuone"),
    ("utility room", False, "kodinhoitohuone"),
    ("sauna", False, "sauna"),
    ("balcony", True, "parveke"),
    ("terrace", True, "terassi"),
]:
    for _name in _names.split("|"):
        _FINNISH_NAMES[_fold(_name)] = (_category, _outdoor)
_ROOM_NAMES.update(_FINNISH_NAMES)

FUZZY_MIN_LETTERS = 6  # "sauma" (a seam) is one edit from "sauna", so 5 letters is too few
_FUZZY_NAMES = [n for n in _FINNISH_NAMES if len(n) >= FUZZY_MIN_LETTERS and n.isalpha()]

_UNIT = re.compile(
    r"^(?:App\.?|Apt\.?|Whg\.?|Apartment|Appartement|Wohnung|Appartamento)\s+([A-Z0-9]{1,3})$",
    re.IGNORECASE,
)


def lookup_room_name(text: str, fuzzy: bool = False) -> tuple[str, bool] | None:
    """A printed room name -> (category, is_outdoor). Exact match, ignoring case,
    spacing and accents (an OCR without accented letters reads "Pièce" as "Piece").

    `fuzzy` (for OCR text) also accepts one misread letter in a Finnish name of at
    least `FUZZY_MIN_LETTERS` letters, when exactly one name is that close.
    """
    key = _fold(text)
    exact = _ROOM_NAMES.get(key)
    if exact is not None or not fuzzy or len(key) < FUZZY_MIN_LETTERS - 1:
        return exact
    close = [n for n in _FUZZY_NAMES if _within_one_edit(key, n)]
    return _FINNISH_NAMES[close[0]] if len(close) == 1 else None


def is_fuzzy_room_name(text: str) -> bool:
    """True when `text` names a room only through the one-edit OCR match."""
    return lookup_room_name(text) is None and lookup_room_name(text, fuzzy=True) is not None


def _within_one_edit(a: str, b: str) -> bool:
    """One substitution, insertion or deletion turns `a` into `b` (or they are equal)."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    if len(a) == len(b):
        return a[i + 1 :] == b[i + 1 :]
    return a[i:] == b[i + 1 :]


def unit_label(text: str) -> str | None:
    """ "App. A" / "Whg. B" / "Apartment 12" -> the unit's id."""
    match = _UNIT.match(" ".join(text.split()))
    return match.group(1).upper() if match else None


_NUMBERED = re.compile(r"^(\D{2,}?)(\d{1,2})$")  # "S1" is more often a section mark


def _code_key(text: str) -> str:
    return text.strip().rstrip(".").upper().replace(" ", "")


def lookup_code(text: str) -> Code | None:
    """Look up a room or fixture code; tolerates case, spaces, trailing dots and a
    room number after a room code ("MH1")."""
    split = room_code_number(text)
    return CODES.get(split[0]) if split else CODES.get(_code_key(text))


def room_code_number(text: str) -> tuple[str, str | None] | None:
    """A room code and the number printed after it: "MH2" -> ("MH", "2"), "KPH" ->
    ("KPH", None). None when `text` is not a room code."""
    key = _code_key(text)
    code = CODES.get(key)
    if code is not None:
        return (key, None) if code.kind == "room" else None
    match = _NUMBERED.match(key)
    if match and (numbered := CODES.get(match.group(1))) and numbered.kind == "room":
        return match.group(1), match.group(2)
    return None


def door_width_mm(text: str) -> int | None:
    """Door tags give the leaf width in modules of 100 mm: "09" is a 900 mm door.

    Only zero-padded 06-09 and 10-12 count, so grid labels like "3" are ignored.
    """
    match = _DOOR_TAG.match(text.strip())
    return int(match.group(1)) * 100 if match else None
