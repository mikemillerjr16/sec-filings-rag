"""Unit tests for prompt/context formatting (pure, offline). The live chain is exercised manually
and by the eval harness (Phase 4)."""

from enterprise_rag.generation.prompts import format_context, source_citation
from enterprise_rag.retrieval.store import SearchHit

HIT = SearchHit(
    chunk_id="NVDA-2026-Item1A-3",
    text="Long manufacturing lead times and uncertain supply may harm our business.",
    score=0.7312,
    metadata={
        "ticker": "NVDA",
        "form": "10-K",
        "fiscal_year": "2026",
        "item": "Item 1A",
        "section_title": "Risk Factors",
        "source_url": "https://sec.gov/x.htm",
    },
)


def test_format_context_numbers_and_labels_sources() -> None:
    ctx = format_context([HIT, HIT])
    assert "[1] NVDA 10-K FY2026 — Item 1A Risk Factors" in ctx
    assert "[2] NVDA 10-K FY2026 — Item 1A Risk Factors" in ctx
    assert "Long manufacturing lead times" in ctx


def test_source_citation_shape() -> None:
    c = source_citation(1, HIT)
    assert c["n"] == 1
    assert c["ticker"] == "NVDA"
    assert c["item"] == "Item 1A"
    assert c["source_url"] == "https://sec.gov/x.htm"
    assert c["score"] == 0.7312
