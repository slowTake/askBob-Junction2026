"""Server-sent event framing and answer-cache keys."""

import hashlib
import json
from typing import Any


def sse(event: str, data: Any) -> str:
    """One SSE frame. JSON never contains raw newlines, so a single data line is safe."""
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def answer_cache_key(
    question: str, document_versions: list[str], model: str, answer_format: int
) -> str:
    """Same question (ignoring case and spacing) over the same document versions,
    model and answer format (bump the format when the answer payload changes)."""
    normalized = " ".join(question.lower().split())
    payload = json.dumps([normalized, sorted(document_versions), model, answer_format])
    return "answer:" + hashlib.sha256(payload.encode()).hexdigest()
