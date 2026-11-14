"""The /api/ask payload carries the agent's numeric value and unit (#41)."""

from app.qa.agent import ANSWER_SCHEMA, FinalAnswer
from app.qa.service import _payload
from app.qa.tools import ToolContext


def _answer(value: float | None, unit: str | None) -> FinalAnswer:
    return FinalAnswer(
        answer="There are 3 bedrooms.",
        value=value,
        unit=unit,
        citations=[],
        confidence="high",
        caveats="",
    )


def _ctx() -> ToolContext:
    return ToolContext(db=None, scope=[])  # type: ignore[arg-type]  # _payload never queries


def test_payload_carries_value_and_unit() -> None:
    payload = _payload(_answer(3, "count"), _ctx())
    assert payload["value"] == 3
    assert payload["unit"] == "count"


def test_payload_value_is_null_for_a_text_answer() -> None:
    payload = _payload(_answer(None, None), _ctx())
    assert payload["value"] is None
    assert payload["unit"] is None


def test_schema_requires_value_and_unit() -> None:
    # Structured outputs need every property listed as required; null stands for "none".
    required = ANSWER_SCHEMA["required"]
    assert isinstance(required, list)
    assert {"value", "unit"} <= set(required)
