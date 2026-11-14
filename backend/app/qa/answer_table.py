"""Structured answer tables shared by both providers; no Markdown table parsing."""

from typing import Self

from pydantic import BaseModel, Field, model_validator

TABLE_SCHEMA = {
    "type": "object",
    "properties": {
        "columns": {"type": "array", "items": {"type": "string"}},
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cells": {"type": "array", "items": {"type": "string"}},
                    "citation": {"type": "integer"},
                },
                "required": ["cells", "citation"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["columns", "rows"],
    "additionalProperties": False,
}


class AnswerRow(BaseModel):
    cells: list[str]
    citation: int = Field(ge=0)  # 1-based citation number; 0 for an aggregate row


class AnswerTable(BaseModel):
    columns: list[str] = Field(default_factory=list, max_length=4)
    rows: list[AnswerRow] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def rectangular(self) -> Self:
        if self.rows and not self.columns:
            raise ValueError("table rows need columns")
        if any(len(row.cells) != len(self.columns) for row in self.rows):
            raise ValueError("table rows must match the columns")
        return self
