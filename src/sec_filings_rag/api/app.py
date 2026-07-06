"""FastAPI surface for the RAG pipeline.

Endpoints:
  GET  /health         — liveness probe (used by ALB / Lambda checks)
  POST /query          — buffered answer + sources (the Track-1 Lambda path)
  POST /query/stream   — SSE token stream (the Track-2 ECS true-streaming path)

The Lambda Function URL is public, so a shared-secret header guards the query endpoints whenever a
real secret is configured (see ADR 0005). Ticker input is validated to avoid injecting into the
vector-store filter expression.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sec_filings_rag.config import get_settings
from sec_filings_rag.generation.chain import get_pipeline
from sec_filings_rag.retrieval.retriever import DEFAULT_K

_TICKER_RE = re.compile(r"^[A-Za-z.]{1,6}$")

app = FastAPI(
    title="SEC Filings RAG API",
    description="Ask questions about SEC 10-K filings; get grounded, cited answers.",
    version="0.1.0",
)


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    k: int = Field(default=DEFAULT_K, ge=1, le=20)
    ticker: str | None = Field(
        default=None, description="optional single-company filter, e.g. NVDA"
    )


def require_secret(x_api_key: str | None = Header(default=None)) -> None:
    """Enforce the shared secret when one is configured; a no-op locally (placeholder secret)."""
    s = get_settings()
    if s.auth_enabled and x_api_key != s.api_shared_secret:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


def _validate_ticker(ticker: str | None) -> str | None:
    """Return the normalized ticker or 400 — reject anything unsafe before any work happens."""
    if ticker is None:
        return None
    if not _TICKER_RE.match(ticker):
        raise HTTPException(status_code=400, detail="invalid ticker")
    return ticker.upper()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query", dependencies=[Depends(require_secret)])
def query(req: QueryRequest) -> dict[str, object]:
    ticker = _validate_ticker(req.ticker)  # validate before doing any work
    answer = get_pipeline().answer(req.question, k=req.k, ticker=ticker)
    return {"answer": answer.text, "sources": answer.sources}


@app.post("/query/stream", dependencies=[Depends(require_secret)])
def query_stream(req: QueryRequest) -> StreamingResponse:
    ticker = _validate_ticker(req.ticker)

    def events() -> Iterator[str]:
        for event in get_pipeline().stream(req.question, k=req.k, ticker=ticker):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
