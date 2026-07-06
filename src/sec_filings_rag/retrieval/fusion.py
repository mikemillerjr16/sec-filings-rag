"""Reciprocal Rank Fusion (RRF).

Combines several ranked result lists (here: dense vector + lexical BM25) using only their ranks,
not their scores — which is exactly why it's robust when the two rankers produce incomparable score
scales. score(d) = sum over lists of 1 / (k + rank(d)). k=60 is the value from the original RRF
paper (Cormack et al., 2009).
"""

from __future__ import annotations

from dataclasses import replace

from sec_filings_rag.retrieval.store import SearchHit

RRF_K = 60


def reciprocal_rank_fusion(
    rankings: list[list[SearchHit]], k: int = RRF_K, top_n: int | None = None
) -> list[SearchHit]:
    """Fuse ranked lists by chunk_id. The returned hits carry the fused RRF score."""
    fused: dict[str, float] = {}
    best_hit: dict[str, SearchHit] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking):
            fused[hit.chunk_id] = fused.get(hit.chunk_id, 0.0) + 1.0 / (k + rank + 1)
            # keep the richest copy of the hit (any list's is fine; text/metadata are identical)
            best_hit.setdefault(hit.chunk_id, hit)

    ordered = sorted(fused, key=lambda cid: fused[cid], reverse=True)
    if top_n is not None:
        ordered = ordered[:top_n]
    return [replace(best_hit[cid], score=fused[cid]) for cid in ordered]
