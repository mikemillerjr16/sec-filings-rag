"""Retriever assembly.

Phase 2 baseline: dense vector search over LanceDB. Phase 3 extends this with hybrid BM25+vector
RRF fusion and a reranker — behind this same `retrieve()` signature, so the generation chain and API
never change. Optional metadata filtering (e.g. a single ticker) powers cross-filing questions.
"""

from __future__ import annotations

from sec_filings_rag.config import Settings, get_settings
from sec_filings_rag.retrieval.embeddings import embed_query
from sec_filings_rag.retrieval.store import SearchHit, get_store

DEFAULT_K = 8


class Retriever:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._store = get_store(self._settings)

    def retrieve(self, query: str, k: int = DEFAULT_K, where: str | None = None) -> list[SearchHit]:
        return self._store.search(embed_query(query), k=k, where=where)
