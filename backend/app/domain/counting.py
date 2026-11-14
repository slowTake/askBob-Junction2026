"""Counting rules for "how many" questions. Pure; used by the `count_elements` tool.

The server counts so the model only reports the number: the total is exact however
many elements match, while only the first `list_max` are listed for citing. Those are
the first by document, page and id, so the same question lists the same elements.
"""

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class Countable:
    element_id: str
    kind: str
    page_index: int | None
    storey: str | None  # IFC building storey name, e.g. "3. Sal"
    subtype: str | None  # fixtures: "wc", "washbasin", "sink", "bathtub", ...
    category: str | None  # rooms: vocabulary category, e.g. "kitchen", "balcony"
    label: str | None  # the printed name, e.g. "Küche"; on an IFC space its number, "005"
    name: str | None = None  # the stored name; on an IFC space its LongName, "Kitchen"
    document_id: str = ""  # page indexes start at 0 in every document


@dataclass(frozen=True)
class CountResult:
    total: int
    by_page: dict[tuple[str, int], int]  # (document id, page index): count
    by_storey: dict[str, int]
    listed: list[Countable]


def _norm(value: str | None) -> str | None:
    """Ignore case and runs of spaces: "Soggiorno /  pranzo" equals "soggiorno / pranzo"."""
    return " ".join(value.split()).casefold() if value is not None else None


def _matches(wanted: str | None, actual: str | None) -> bool:
    return wanted is None or (actual is not None and _norm(wanted) == _norm(actual))


def _listing_order(c: Countable) -> tuple[str, bool, int, str]:
    """Document, then page (elements without a page last), then id."""
    return (c.document_id, c.page_index is None, c.page_index or 0, c.element_id)


def count(
    items: list[Countable],
    kind: str,
    *,
    subtype: str | None = None,
    category: str | None = None,
    name: str | None = None,
    storey: str | None = None,
    page_index: int | None = None,
    list_max: int = 50,
) -> CountResult:
    """Count the elements of `kind` that match every given filter.

    `name` matches the printed label or the stored name exactly (ignoring case and
    runs of spaces), so "Küche" does not count "Wohnküche". An element without a
    property never matches a filter on it.
    """
    picked = [
        c
        for c in items
        if c.kind == kind
        and _matches(subtype, c.subtype)
        and _matches(category, c.category)
        and (_matches(name, c.label) or _matches(name, c.name))
        and _matches(storey, c.storey)
        and (page_index is None or c.page_index == page_index)
    ]
    picked.sort(key=_listing_order)
    by_page = Counter((c.document_id, c.page_index) for c in picked if c.page_index is not None)
    by_storey = Counter(c.storey for c in picked if c.storey is not None)
    return CountResult(len(picked), dict(by_page), dict(by_storey), picked[:list_max])
