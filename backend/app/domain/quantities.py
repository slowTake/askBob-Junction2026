"""IFC base quantities in SI units, and totals over them. Pure; used by the IFC
indexer and the `sum_quantity` tool.

The server adds up, so the model only reports the number: the total is exact however
many elements match, while only the first `list_max` are listed for citing.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# Lengths have no common suffix in IFC's base quantities, so they are named.
_LENGTHS = frozenset(
    {"Length", "Width", "Height", "Depth", "Perimeter", "GrossPerimeter", "NetPerimeter"}
)
DECIMALS = 4  # stored per element: a tenth of a millimetre, a square centimetre
TOTAL_DECIMALS = 3  # the dataset's answers have three


def unit_of(quantity: str) -> str | None:
    """ "NetVolume" -> "m3", "NetSideArea" -> "m2", "Length" -> "m"; None if not one of ours."""
    if quantity.endswith("Volume"):
        return "m3"
    if quantity.endswith("Area"):
        return "m2"
    return "m" if quantity in _LENGTHS else None


def _is_base_set(name: Any) -> bool:
    """IFC4 `Qto_*` sets and IFC2X3 `BaseQuantities`. Authoring tools' own quantity sets
    (ArchiCADQuantities, ...) reuse names like "Area" with other meanings: left out."""
    return isinstance(name, str) and (name.startswith("Qto_") or name == "BaseQuantities")


def base_quantities(
    psets: Mapping[Any, Mapping[Any, Any]], to_m: float, to_m2: float, to_m3: float
) -> dict[str, float]:
    """Lengths, areas and volumes of an element's base quantity sets, in m, m² and m³.

    `to_m`, `to_m2` and `to_m3` are the model's unit scales. Anything that is not a
    number, or not a length, area or volume (weights, counts), is left out.
    """
    scale = {"m": to_m, "m2": to_m2, "m3": to_m3}
    out: dict[str, float] = {}
    for name, values in psets.items():
        if not _is_base_set(name):
            continue
        for key, value in values.items():
            unit = unit_of(key) if isinstance(key, str) else None
            if unit is None or isinstance(value, bool) or not isinstance(value, int | float):
                continue
            out.setdefault(key, round(float(value) * scale[unit], DECIMALS))
    return out


@dataclass(frozen=True)
class Measured:
    element_id: str
    kind: str
    storey: str | None  # IFC building storey name, e.g. "3. Sal"
    quantities: Mapping[str, float]  # SI units, from `base_quantities`


@dataclass(frozen=True)
class QuantityTotal:
    total: float
    unit: str | None
    summed: int  # elements that had the quantity
    missing: int  # elements the filters selected that did not have it
    by_storey: dict[str, float]
    listed: list[Measured]


def _norm(value: str) -> str:
    return " ".join(value.split()).casefold()


def total_quantity(
    items: list[Measured],
    kind: str,
    quantity: str,
    *,
    storey: str | None = None,
    list_max: int = 50,
) -> QuantityTotal:
    """Add up `quantity` over the elements of `kind`, optionally on one storey.

    The storey name ignores case and runs of spaces. Elements without the quantity are
    counted in `missing`, so a total over half the walls is not mistaken for all of them.
    """
    selected = [
        m
        for m in items
        if m.kind == kind
        and (storey is None or (m.storey is not None and _norm(m.storey) == _norm(storey)))
    ]
    having = [m for m in selected if quantity in m.quantities]
    by_storey: dict[str, float] = defaultdict(float)
    for m in having:
        if m.storey is not None:
            by_storey[m.storey] += m.quantities[quantity]
    return QuantityTotal(
        total=round(sum(m.quantities[quantity] for m in having), TOTAL_DECIMALS),
        unit=unit_of(quantity),
        summed=len(having),
        missing=len(selected) - len(having),
        by_storey={name: round(value, TOTAL_DECIMALS) for name, value in by_storey.items()},
        listed=having[:list_max],
    )
