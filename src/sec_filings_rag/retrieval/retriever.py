"""Hybrid retriever: dense vector + lexical BM25 -> RRF fusion -> rerank.

This is the Phase 3 upgrade over the Phase 2 dense-only baseline. From the caller's view the seam is
the same (it now takes a structured `ticker` filter instead of a raw where clause), so the
generation chain and API didn't change shape. BM25 is in-application, so the exact same fusion path
runs on both the LanceDB and pgvector backends (ADR 0007).
"""

from __future__ import annotations

import re

from sec_filings_rag.config import Settings, get_settings
from sec_filings_rag.retrieval.bm25 import BM25Index, bm25_dir_for
from sec_filings_rag.retrieval.embeddings import embed_query
from sec_filings_rag.retrieval.fusion import reciprocal_rank_fusion
from sec_filings_rag.retrieval.rerank import get_reranker
from sec_filings_rag.retrieval.store import SearchHit, get_store

DEFAULT_K = 8  # final results handed to the LLM
CANDIDATE_K = 24  # candidates pulled from each arm before fusion + rerank

_TICKER_RE = re.compile(r"^[A-Za-z.]{1,6}$")


class Retriever:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._store = get_store(self._settings)
        self._bm25 = BM25Index(bm25_dir_for(self._settings.lancedb_uri))
        self._reranker = get_reranker(self._settings)

    def retrieve(
        self,
        query: str,
        k: int = DEFAULT_K,
        ticker: str | None = None,
        candidate_k: int = CANDIDATE_K,
    ) -> list[SearchHit]:
        ticker = _clean_ticker(ticker)
        where = f"ticker = '{ticker}'" if ticker else None

        vector_hits = self._store.search(embed_query(query), k=candidate_k, where=where)
        bm25_hits = self._bm25.search(query, k=candidate_k)
        if ticker:  # BM25 has no server-side filter; apply the same restriction post hoc
            bm25_hits = [h for h in bm25_hits if h.metadata.get("ticker") == ticker]

        fused = reciprocal_rank_fusion([vector_hits, bm25_hits], top_n=candidate_k)
        return self._reranker.rerank(query, fused, top_n=k)


def _clean_ticker(ticker: str | None) -> str | None:
    """Validate + normalize; refuse anything that could inject into the filter expression."""
    if ticker is None:
        return None
    if not _TICKER_RE.match(ticker):
        raise ValueError(f"invalid ticker: {ticker!r}")
    return ticker.upper()
