"""Unit tests for parsing + chunking, using a tiny synthetic iXBRL-style 10-K fixture.

Keeps CI offline and fast; the real end-to-end fetch is exercised by `make ingest`.
"""

from sec_filings_rag.ingestion.chunk import chunk_filing
from sec_filings_rag.ingestion.edgar import Filing
from sec_filings_rag.ingestion.parse import parse_sections

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


# Microsoft-style filing: TOC link text is the SECTION NAME, and only the href fragment carries
# the item number. Regression guard so this filer convention keeps parsing.
MSFT_STYLE_HTML = """
<html><body>
  <div>
    <a href="#item_1_business">Business</a>
    <a href="#item_1a_risk_factors">Risk Factors</a>
    <a href="#item5_market">Market for Registrant's Common Equity</a>
  </div>
  <div id="item_1_business"><p>We develop and license software and cloud services.</p></div>
  <div id="item_1a_risk_factors"><p>Cybersecurity threats could disrupt our cloud operations.</p></div>
  <div id="item5_market"><p>Our common stock is listed on the Nasdaq under MSFT.</p></div>
</body></html>
"""


def test_parse_handles_href_encoded_items() -> None:
    sections = parse_sections(MSFT_STYLE_HTML)
    assert [s.item for s in sections] == ["Item 1", "Item 1A", "Item 5"]
    # link text becomes the section title for this convention
    assert sections[1].title == "Risk Factors"
    assert "Cybersecurity threats" in sections[1].text


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
