"""End-to-end ingestion: SEC EDGAR -> parse -> chunk -> embed -> LanceDB + BM25.

Idempotent: each run rebuilds both indexes from the requested filings, so re-running is safe.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sec_filings_rag.config import get_settings
from sec_filings_rag.ingestion import edgar
from sec_filings_rag.ingestion.chunk import chunk_filing, chunk_to_record
from sec_filings_rag.ingestion.parse import parse_sections
from sec_filings_rag.retrieval.bm25 import BM25Index, bm25_dir_for
from sec_filings_rag.retrieval.embeddings import embed_texts
from sec_filings_rag.retrieval.store import get_store

DEFAULT_TICKERS = ["NVDA", "AMD", "MSFT"]

log = logging.getLogger("sec_filings_rag.ingest")


@dataclass
class IngestReport:
    tickers: list[str] = field(default_factory=list)
    filings: int = 0
    chunks: int = 0
    vector_rows: int = 0
    bm25_docs: int = 0

    def __str__(self) -> str:
        return (
            f"ingested {self.filings} filings ({', '.join(self.tickers)}) -> "
            f"{self.chunks} chunks | vector store: {self.vector_rows} rows | "
            f"BM25: {self.bm25_docs} docs"
        )


def ingest(tickers: list[str] | None = None) -> IngestReport:
    settings = get_settings()
    tickers = tickers or DEFAULT_TICKERS
    report = IngestReport(tickers=list(tickers))

    all_chunks = []
    for ticker in tickers:
        log.info("fetching %s 10-K from EDGAR ...", ticker)
        filing, path = edgar.fetch(ticker)
        sections = parse_sections(path.read_text(encoding="utf-8"))
        chunks = chunk_filing(filing, sections)
        log.info(
            "  %s FY%s: %d sections -> %d chunks",
            ticker,
            filing.fiscal_year,
            len(sections),
            len(chunks),
        )
        # Fail loud, never silently: a filing that parses to nothing means the parser doesn't yet
        # handle this filer's structure. Better to stop than build an index missing a company.
        if not chunks:
            raise RuntimeError(
                f"{ticker} parsed to 0 chunks — the parser does not handle this filing's structure "
                f"(source: {filing.url}). Fix parsing before building the index."
            )
        all_chunks.extend(chunks)
        report.filings += 1

    report.chunks = len(all_chunks)
    if not all_chunks:
        raise RuntimeError("no chunks produced — check parsing")

    log.info("embedding %d chunks ...", len(all_chunks))
    vectors = embed_texts([c.text for c in all_chunks])
    records = [
        {**chunk_to_record(c), "vector": v} for c, v in zip(all_chunks, vectors, strict=True)
    ]

    log.info("writing vector store (%s) ...", settings.store_backend)
    store = get_store(settings)
    store.write(records)
    report.vector_rows = store.count()

    log.info("building in-app BM25 index ...")
    bm25 = BM25Index(bm25_dir_for(settings.lancedb_uri))
    bm25.build(records)
    report.bm25_docs = bm25.count()

    log.info("done: %s", report)
    return report
