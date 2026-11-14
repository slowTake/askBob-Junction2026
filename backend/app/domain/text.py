"""Fit free text into bounded database columns."""

ELLIPSIS = "…"


def clip(value: str | None, limit: int) -> str | None:
    """Cut `value` to at most `limit` characters, ending in "…" when something was cut."""
    if value is None or len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)] + ELLIPSIS
