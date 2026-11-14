"""Glue for /api/ask: scope, answer cache (Valkey), agent run, citation check, Q&A log."""

import json
import logging
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import anthropic
import openai
from sqlalchemy import select

from app.config import Settings, get_settings
from app.db import session_scope
from app.domain.citations import Citation, check_citations, citation_payload
from app.domain.streams import answer_cache_key, sse
from app.domain.usage import Usage
from app.models import Document, Element, Page, QaLog
from app.qa.agent import AgentError, FinalAnswer, run_agent
from app.qa.fast_path import fast_events
from app.qa.prompts import SelectedElement, selected_notes, viewing_note
from app.qa.tools import ToolContext
from app.qa.verda_agent import run_verda_agent
from app.schemas import AskContextIn
from app.valkey import cache_get, cache_set

log = logging.getLogger(__name__)

ANSWER_FORMAT = 5  # bump when the payload or how answers are found changes
# 4: answers are a summary line plus "- " lists (prompts.py), laid out by the chat
# 5: answers say how they were found (`method`: the agent or the server's fast path)

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


def answer_stream(
    question: str, document_ids: list[str], context: AskContextIn | None = None
) -> Iterator[str]:
    settings = get_settings()
    started = time.monotonic()
    record: dict[str, Any] = {"question": question, "document_ids": document_ids,
                              "model": settings.llm_model}  # fmt: skip
    ctx: ToolContext | None = None
    steps = 0
    method = "agent"  # or "server": answered without the agent loop (D-029)
    try:
        with session_scope() as db:
            docs = _scope(db, document_ids)
            if not docs:
                raise AgentError("no_documents")
            viewing, selected = _context_notes(db, docs, context)
            versions = [f"{d.id}@{d.version}" for d in docs]
            key = answer_cache_key(
                question,
                versions,
                settings.llm_model,
                ANSWER_FORMAT,
                f"{viewing or ''}|{'|'.join(selected)}",  # one element: same key as before
            )
            cached = cache_get(key)
            if cached is not None:
                record.update(answer=cached, verified=cached.get("verified", False), cached=True)
                method = cached.get("method", "agent")
                yield sse("answer", {**cached, "cached": True})
            else:
                ctx = ToolContext(db, [d.id for d in docs])
                summaries = [{"id": str(d.id), "filename": d.filename, "kind": d.kind,
                              "page_count": d.page_count} for d in docs]  # fmt: skip
                events = fast_events(question, summaries, ctx, settings, selected)
                if events is not None:
                    method = "server"
                run = events or _agent(settings)(
                    question, summaries, ctx, settings, viewing, selected
                )
                for event in run:
                    if event["type"] == "step":
                        steps += 1
                        yield sse("step", {"tool": event["tool"], "input": event["input"]})
                        continue
                    if event["type"] == "view":
                        yield sse("view", event["view"])
                        continue
                    payload = {**_payload(event["answer"], ctx), "method": method}
                    record.update(answer=payload, verified=payload["verified"])
                    cache_set(key, payload, settings.answer_cache_ttl_s)
                    yield sse("answer", payload)
    except AgentError as exc:
        record["error_code"] = exc.code
        yield _error(exc.code)
    except (anthropic.AuthenticationError, openai.AuthenticationError):
        log.exception("llm credentials rejected")
        record["error_code"] = "llm_not_configured"
        yield _error("llm_not_configured")
    except (anthropic.RateLimitError, openai.RateLimitError):
        log.warning("llm rate limited", exc_info=True)
        record["error_code"] = "llm_busy"
        yield _error("llm_busy")
    except (anthropic.APIStatusError, anthropic.APIConnectionError,
            openai.APIStatusError, openai.APIConnectionError):  # fmt: skip
        log.exception("llm request failed")
        record["error_code"] = "llm_unavailable"
        yield _error("llm_unavailable")
    except Exception:
        log.exception("ask failed")
        record["error_code"] = "internal_error"
        yield _error("internal_error")
    # Usage is read after the run, so a failed question reports what it used too.
    usage = ctx.usage if ctx is not None else Usage()
    record["latency_ms"] = int((time.monotonic() - started) * 1000)
    record.update(input_tokens=usage.total_input_tokens, output_tokens=usage.output_tokens)
    _log(record)
    served_from_cache = bool(record.get("cached"))
    stats = _stats(settings.llm_model, usage, steps, record["latency_ms"], served_from_cache)
    stats["method"] = method
    yield sse("done", stats)


def _stats(model: str, usage: Usage, steps: int, latency_ms: int, cached: bool) -> dict[str, Any]:
    """What answering took, for the eval and for anyone comparing models (#98)."""
    return {"model": model, "cached": cached, "steps": steps, "latency_ms": latency_ms,
            **usage.as_dict()}  # fmt: skip


def _agent(settings: Settings) -> Callable[..., Iterator[dict[str, Any]]]:
    """The model loop for the configured provider; both emit the same events (D-020)."""
    return run_verda_agent if settings.llm_provider == "verda" else run_agent


def _scope(db: Any, document_ids: list[str]) -> list[Document]:
    query = select(Document).where(Document.status == "ready")
    if document_ids:
        query = query.where(Document.id.in_([uuid.UUID(d) for d in document_ids]))
    return list(db.scalars(query.order_by(Document.created_at)).all())


def _context_notes(
    db: Any, docs: list[Document], context: AskContextIn | None
) -> tuple[str | None, list[str]]:
    """Describe the page on screen and the selected elements that are in scope."""
    if context is None:
        return None, []
    in_scope = {d.id: d for d in docs}
    viewing = None
    doc = in_scope.get(context.document_id) if context.document_id else None
    if doc is not None and context.page_index is not None:
        page = db.scalar(
            select(Page).where(Page.document_id == doc.id, Page.index == context.page_index)
        )
        if page is not None:
            label = page.meta.get("storey")
            viewing = viewing_note(
                doc.filename, str(doc.id), page.index, doc.page_count, str(label) if label else None
            )
    ids = context.selected_ids()
    if not ids:
        return viewing, []
    # One query for every selected element and its page (PR #92 review: it was two per
    # element, up to 40 round trips before every ask, cache hits included).
    rows = db.execute(
        select(Element, Page.index)
        .outerjoin(Page, Page.id == Element.page_id)
        .where(Element.id.in_(ids))
    ).all()
    found = {
        str(el.id): SelectedElement(
            str(el.id), str(el.document_id), el.kind, el.text or el.name or el.label, index
        )
        for el, index in rows
    }
    return viewing, selected_notes([str(i) for i in ids], found, {str(d) for d in in_scope})


def _payload(answer: FinalAnswer, ctx: ToolContext) -> dict[str, Any]:
    citations = [
        Citation(c.element_id, c.page_id,
                 (c.bbox.x0, c.bbox.y0, c.bbox.x1, c.bbox.y1) if c.bbox else None, c.note)
        for c in answer.citations
    ]  # fmt: skip
    checked, verified = check_citations(citations, ctx.elements, ctx.regions)
    return {
        "answer": answer.answer,
        "value": answer.value,
        "unit": answer.unit,
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
