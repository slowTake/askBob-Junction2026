"""Reject malformed inventories before they reach the UI; keep old answers readable."""

import pytest
from pydantic import ValidationError

from app.qa.answer_table import AnswerTable


def test_empty_table_and_cited_inventory() -> None:
    assert AnswerTable().model_dump() == {"columns": [], "rows": []}
    table = AnswerTable.model_validate(
        {
            "columns": ["Window", "Width (mm)"],
            "rows": [{"cells": ["W1", "900"], "citation": 1}],
        }
    )
    assert table.rows[0].citation == 1
    assert table.rows[0].cells == ["W1", "900"]


@pytest.mark.parametrize(
    "raw",
    [
        {"columns": [], "rows": [{"cells": [], "citation": 0}]},
        {"columns": ["Window"], "rows": [{"cells": ["W1", "900"], "citation": 1}]},
        {"columns": ["Window"], "rows": [{"cells": ["W1"], "citation": -1}]},
        {"columns": ["a"] * 5, "rows": []},
        {"columns": ["Window"], "rows": [{"cells": ["W1"], "citation": 1}] * 51},
    ],
)
def test_rejects_invalid_tables(raw: dict) -> None:
    with pytest.raises(ValidationError):
        AnswerTable.model_validate(raw)
