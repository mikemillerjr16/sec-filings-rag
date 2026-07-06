"""In-app BM25 lexical index (bm25s).

BM25 is kept in-application (not delegated to Postgres full-text) so the hybrid-fusion code path is
identical on both the LanceDB and pgvector backends — only the *vector* store swaps. See ADR 0007.
The index plus an aligned records file are persisted to a directory that can live locally or be
synced from S3 on Track 1.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import bm25s

from sec_filings_rag.retrieval.store import SearchHit

_STOPWORDS = "en"


class BM25Index:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._retriever: bm25s.BM25 | None = None
        self._records: list[dict[str, Any]] = []

    # --- build / persist ---
    def build(self, records: list[dict[str, Any]]) -> None:
        if not records:
            raise ValueError("no records to index")
        texts = [r["text"] for r in records]
        tokens = bm25s.tokenize(texts, stopwords=_STOPWORDS, show_progress=False)
        retriever = bm25s.BM25()
        retriever.index(tokens, show_progress=False)

        self.path.mkdir(parents=True, exist_ok=True)
        retriever.save(str(self.path / "index"))
        # Persist records WITHOUT the embedding vector; aligned to BM25 doc ids by list order.
        with (self.path / "records.jsonl").open("w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps({k: v for k, v in r.items() if k != "vector"}) + "\n")
        self._retriever, self._records = retriever, records

    # --- load / query ---
    def _ensure_loaded(self) -> None:
        if self._retriever is not None:
            return
        self._retriever = bm25s.BM25.load(str(self.path / "index"))
        with (self.path / "records.jsonl").open(encoding="utf-8") as fh:
            self._records = [json.loads(line) for line in fh]

    def search(self, query: str, k: int = 10) -> list[SearchHit]:
        self._ensure_loaded()
        assert self._retriever is not None
        n = len(self._records)
        if n == 0:
            return []
        tokens = bm25s.tokenize(query, stopwords=_STOPWORDS, show_progress=False)
        idxs, scores = self._retriever.retrieve(tokens, k=min(k, n), show_progress=False)
        hits: list[SearchHit] = []
        for doc_idx, score in zip(idxs[0], scores[0], strict=True):
            rec = self._records[int(doc_idx)]
            meta = {kk: vv for kk, vv in rec.items() if kk != "text"}
            hits.append(
                SearchHit(
                    chunk_id=str(rec.get("chunk_id", "")),
                    text=str(rec.get("text", "")),
                    score=float(score),
                    metadata=meta,
                )
            )
        return hits

    def count(self) -> int:
        self._ensure_loaded()
        return len(self._records)


def bm25_dir_for(lancedb_uri: str) -> Path:
    """Sibling 'bm25' directory next to the LanceDB store (local paths only for now)."""
    return Path(lancedb_uri).parent / "bm25"
