"""Reranking — a cross-encoder pass over the fused candidates for final ordering.

Deliberate Track split (ADR 0006):
- **Cohere Rerank API** on Track 1 — a network call, no heavy dependencies, so the scale-to-zero
  Lambda image stays small and cold starts stay fast.
- **Local cross-encoder** (sentence-transformers) for local dev and Track 2 only — pulls in torch,
  which would bloat the Lambda image, so it's an optional dependency group.
- **Noop** passthrough when reranking is disabled or unavailable, so the pipeline still works.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Protocol

from sec_filings_rag.config import RerankBackend, Settings, get_settings
from sec_filings_rag.retrieval.store import SearchHit

log = logging.getLogger("sec_filings_rag.rerank")

COHERE_MODEL = "rerank-v3.5"
LOCAL_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class Reranker(Protocol):
    def rerank(self, query: str, hits: list[SearchHit], top_n: int) -> list[SearchHit]: ...


class NoopReranker:
    """Keeps the fused order; just truncates to top_n."""

    def rerank(self, query: str, hits: list[SearchHit], top_n: int) -> list[SearchHit]:
        return hits[:top_n]


class CohereReranker:
    def __init__(self, api_key: str, model: str = COHERE_MODEL) -> None:
        import cohere

        self._client = cohere.ClientV2(api_key)
        self._model = model

    def rerank(self, query: str, hits: list[SearchHit], top_n: int) -> list[SearchHit]:
        if not hits:
            return []
        resp = self._client.rerank(
            model=self._model,
            query=query,
            documents=[h.text for h in hits],
            top_n=min(top_n, len(hits)),
        )
        return [replace(hits[r.index], score=r.relevance_score) for r in resp.results]


class LocalCrossEncoderReranker:
    """sentence-transformers cross-encoder. Optional dep group `rerank-local` (installs torch)."""

    def __init__(self, model: str = LOCAL_MODEL) -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model)

    def rerank(self, query: str, hits: list[SearchHit], top_n: int) -> list[SearchHit]:
        if not hits:
            return []
        scores = self._model.predict([(query, h.text) for h in hits])
        ranked = sorted(zip(hits, scores, strict=True), key=lambda x: x[1], reverse=True)
        return [replace(h, score=float(s)) for h, s in ranked[:top_n]]


_RERANKER: Reranker | None = None


def get_reranker(settings: Settings | None = None) -> Reranker:
    """Process-wide reranker singleton (model load / client init happens once)."""
    global _RERANKER
    if _RERANKER is not None:
        return _RERANKER
    _RERANKER = _build_reranker(settings or get_settings())
    return _RERANKER


def _build_reranker(s: Settings) -> Reranker:
    backend = s.rerank_backend
    if backend is RerankBackend.cohere:
        if not s.cohere_api_key:
            log.warning("rerank_backend=cohere but COHERE_API_KEY is unset — reranking disabled")
            return NoopReranker()
        return CohereReranker(s.cohere_api_key)
    if backend is RerankBackend.local:
        try:
            return LocalCrossEncoderReranker()
        except ImportError:
            log.warning("local reranker needs the 'rerank-local' group (torch) — reranking disabled")
            return NoopReranker()
    return NoopReranker()
