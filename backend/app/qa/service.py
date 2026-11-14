"""Glue for /api/ask: scope, answer cache (Valkey), agent run, citation check, Q&A log."""

import json
import logging
import time
import uuid
from collections.abc import Iterator
from typing import Any

import anthropic
from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.domain.citations import Citation, check_citations, citation_payload
from app.domain.streams import answer_cache_key, sse
from app.models import Document, QaLog
from app.qa.agent import AgentError, FinalAnswer, run_agent
from app.qa.tools import ToolContext
from app.valkey import cache_get, cache_set

log = logging.getLogger(__name__)

MESSAGES = {
    "no_documents": "Upload a drawing and wait until it has been processed.",
    "refused": "The model declined to answer this question.",
    "too_long": "The answer ran too long. Try a narrower question.",
    "too_many_steps": "Could not find an answer within the step limit. Try a narrower question.",
    "bad_answer": "The model returned an answer we could not read. Please try again.",
    "llm_not_configured": "The language model is not configured on the server.",
    "llm_busy": "The language model is busy. Try again in a minute.",
    "llm_unavailable": "The language model is unavailable right now.",
    "internal_error": "Something went wrong.",
}


def answer_stream(question: str, document_ids: list[str]) -> Iterator[str]:
    settings = get_settings()
    started = time.monotonic()
    record: dict[str, Any] = {"question": question, "document_ids": document_ids,
                              "model": settings.claude_model}  # fmt: skip
    try:
        with session_scope() as db:
            docs = _scope(db, document_ids)
            if not docs:
                raise AgentError("no_documents")
            versions = [f"{d.id}@{d.version}" for d in docs]
            key = answer_cache_key(question, versions, settings.claude_model)
            cached = cache_get(key)
            if cached is not None:
                record.update(answer=cached, verified=cached.get("verified", False), cached=True)
                yield sse("answer", {**cached, "cached": True})
            else:
                ctx = ToolContext(db, [d.id for d in docs])
                summaries = [{"id": str(d.id), "filename": d.filename, "kind": d.kind,
                              "page_count": d.page_count} for d in docs]  # fmt: skip
                for event in run_agent(question, summaries, ctx, settings):
                    if event["type"] == "step":
                        yield sse("step", {"tool": event["tool"], "input": event["input"]})
                        continue
                    if event["type"] == "view":
                        yield sse("view", event["view"])
                        continue
                    payload = _payload(event["answer"], ctx)
                    record.update(answer=payload, verified=payload["verified"], **event["usage"])
                    cache_set(key, payload, settings.answer_cache_ttl_s)
                    yield sse("answer", payload)
    except AgentError as exc:
        record["error_code"] = exc.code
        yield _error(exc.code)
    except anthropic.AuthenticationError:
        log.exception("anthropic credentials rejected")
        record["error_code"] = "llm_not_configured"
        yield _error("llm_not_configured")
    except anthropic.RateLimitError:
        log.warning("anthropic rate limited", exc_info=True)
        record["error_code"] = "llm_busy"
        yield _error("llm_busy")
    except (anthropic.APIStatusError, anthropic.APIConnectionError):
        log.exception("anthropic request failed")
        record["error_code"] = "llm_unavailable"
        yield _error("llm_unavailable")
    except Exception:
        log.exception("ask failed")
        record["error_code"] = "internal_error"
        yield _error("internal_error")
    record["latency_ms"] = int((time.monotonic() - started) * 1000)
    _log(record)
    yield sse("done", {})


def _scope(db: Any, document_ids: list[str]) -> list[Document]:
    query = select(Document).where(Document.status == "ready")
    if document_ids:
        query = query.where(Document.id.in_([uuid.UUID(d) for d in document_ids]))
    return list(db.scalars(query.order_by(Document.created_at)).all())


def _payload(answer: FinalAnswer, ctx: ToolContext) -> dict[str, Any]:
    citations = [
        Citation(c.element_id, c.page_id,
                 (c.bbox.x0, c.bbox.y0, c.bbox.x1, c.bbox.y1) if c.bbox else None, c.note)
        for c in answer.citations
    ]  # fmt: skip
    checked, verified = check_citations(citations, ctx.elements, ctx.regions)
    return {
        "answer": answer.answer,
        "confidence": answer.confidence,
        "caveats": answer.caveats,
        "verified": verified,
        "citations": [citation_payload(c) for c in checked],
        "views": ctx.views,  # replayed from the cache like the rest of the answer
        "cached": False,
    }


def _error(code: str) -> str:
    return sse("error", {"code": code, "message": MESSAGES.get(code, MESSAGES["internal_error"])})


def _log(record: dict[str, Any]) -> None:
    try:
        with session_scope() as db:
            db.add(QaLog(**record))
    except Exception:
        log.warning("could not write qa_log: %s", json.dumps(record, default=str)[:500])
