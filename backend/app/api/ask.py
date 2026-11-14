"""POST /api/ask: stream the agent's steps and its cited answer as server-sent events.

Events: `step` (a tool call), `answer` (final, with checked citations), `error`, `done`.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.events import SSE_HEADERS
from app.qa.service import answer_stream
from app.schemas import AskIn

router = APIRouter(prefix="/api", tags=["ask"])


@router.post("/ask")
def ask(body: AskIn) -> StreamingResponse:
    # A sync generator: Starlette runs it in a worker thread, so blocking DB and
    # Claude calls are fine here.
    stream = answer_stream(body.question, [str(d) for d in body.document_ids], body.context)
    return StreamingResponse(stream, media_type="text/event-stream", headers=SSE_HEADERS)
