"""Offline tests for RRF fusion and the reranker fallback (no network/model needed)."""

from sec_filings_rag.retrieval.fusion import reciprocal_rank_fusion
from sec_filings_rag.retrieval.rerank import NoopReranker
from sec_filings_rag.retrieval.store import SearchHit


def _hit(cid: str) -> SearchHit:
    return SearchHit(chunk_id=cid, text=f"text-{cid}", score=0.0, metadata={"chunk_id": cid})


def test_rrf_rewards_agreement_across_rankings() -> None:
    a = [_hit("h1"), _hit("h2"), _hit("h3")]
    b = [_hit("h2"), _hit("h3"), _hit("h1")]
    fused = reciprocal_rank_fusion([a, b])
    order = [h.chunk_id for h in fused]
    # h2 ranks high in both -> first; h3 lowest combined -> last
    assert order == ["h2", "h1", "h3"]
    assert fused[0].score > fused[1].score > fused[2].score


def test_rrf_dedupes_and_respects_top_n() -> None:
    a = [_hit("h1"), _hit("h2")]
    b = [_hit("h1"), _hit("h3")]
    fused = reciprocal_rank_fusion([a, b], top_n=2)
    assert len(fused) == 2
    assert fused[0].chunk_id == "h1"  # appears in both lists -> top


def test_noop_reranker_truncates_preserving_order() -> None:
    hits = [_hit("h1"), _hit("h2"), _hit("h3")]
    out = NoopReranker().rerank("q", hits, top_n=2)
    assert [h.chunk_id for h in out] == ["h1", "h2"]
