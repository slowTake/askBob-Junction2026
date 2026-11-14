"""State shared by the agent's tools during one question."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.domain.citations import EvidenceItem


@dataclass
class ToolContext:
    db: Session
    scope: list[uuid.UUID]
    elements: dict[str, EvidenceItem] = field(default_factory=dict)
    regions: list[EvidenceItem] = field(default_factory=list)
    views: list[dict[str, Any]] = field(default_factory=list)  # what to show on the plan


class ToolInputError(Exception):
    pass


def parse_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ToolInputError("not a valid id") from exc
