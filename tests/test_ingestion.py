"""Unit tests for parsing + chunking, using a tiny synthetic iXBRL-style 10-K fixture.

Keeps CI offline and fast; the real end-to-end fetch is exercised by `make ingest`.
"""

from enterprise_rag.ingestion.chunk import chunk_filing
from enterprise_rag.ingestion.edgar import Filing
from enterprise_rag.ingestion.parse import parse_sections

# Minimal filing that mimics the real structure: a hyperlinked TOC -> anchor ids, an iXBRL hidden
# header we must strip, an inline ix:nonfraction number we must keep, and a financial table.
FIXTURE_HTML = """
<html><body>
  <ix:header><ix:hidden>0001045810 2026 FY false JUNK METADATA</ix:hidden></ix:header>
  <div>
    <a href="#s1">Item 1.</a>
    <a href="#s1a">Item 1A.</a>
    <a href="#s8">Item 8.</a>
  </div>
  <div id="s1"><span>Item 1. Business</span>
    <p>We design GPUs and accelerated computing platforms for data centers.</p>
  </div>
  <div id="s1a"><span>Item 1A. Risk Factors</span>
    <p>Demand for our products may not meet expectations, which could harm results.</p>
  </div>
  <div id="s8"><span>Item 8. Financial Statements</span>
    <table>
      <tr><td>Revenue</td><td>$</td><td><ix:nonfraction>215,938</ix:nonfraction></td></tr>
      <tr><td>Net income</td><td>$</td><td><ix:nonfraction>120,067</ix:nonfraction></td></tr>
    </table>
  </div>
</body></html>
"""

FILING = Filing(
    ticker="TEST",
    company="Test Corp",
    cik=1,
    form="10-K",
    fiscal_year="2026",
    accession="0000000000-26-000001",
    primary_doc="test.htm",
    url="https://example.com/test.htm",
)


def test_parse_recovers_sections_in_order() -> None:
    sections = parse_sections(FIXTURE_HTML)
    assert [s.item for s in sections] == ["Item 1", "Item 1A", "Item 8"]


def test_parse_strips_ixbrl_header_but_keeps_inline_numbers() -> None:
    sections = parse_sections(FIXTURE_HTML)
    joined = " ".join(s.text for s in sections)
    assert "JUNK METADATA" not in joined  # hidden header stripped
    assert "215,938" in joined  # inline ix:nonfraction value kept


def test_parse_preserves_table_rows() -> None:
    fs = next(s for s in parse_sections(FIXTURE_HTML) if s.item == "Item 8")
    assert "Revenue | $ | 215,938" in fs.text
    assert "Net income | $ | 120,067" in fs.text


def test_chunk_metadata_and_provenance() -> None:
    sections = parse_sections(FIXTURE_HTML)
    chunks = chunk_filing(FILING, sections, max_tokens=64, overlap_tokens=8)
    assert chunks, "expected at least one chunk"
    c = chunks[0]
    assert c.metadata["ticker"] == "TEST"
    assert c.metadata["fiscal_year"] == "2026"
    assert c.metadata["item"].startswith("Item")
    assert c.metadata["chunk_id"].startswith("TEST-2026-Item")
    assert c.metadata["source_url"] == FILING.url
    # chunks never cross section boundaries
    assert all(ch.metadata["item"] in {"Item 1", "Item 1A", "Item 8"} for ch in chunks)
