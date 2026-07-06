"""Structure-aware, token-bounded chunking.

Chunks never cross section boundaries (so a retrieved chunk always has a clean "Item 1A. Risk
Factors" provenance), are sized to the embedding model's tokenizer, and overlap slightly so facts
that straddle a boundary aren't lost. Every chunk carries rich metadata for citations and filtering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import tiktoken

from sec_filings_rag.ingestion.edgar import Filing
from sec_filings_rag.ingestion.parse import Section

_ENCODING = "cl100k_base"  # used by text-embedding-3-* and gpt-4o-*

DEFAULT_MAX_TOKENS = 512
DEFAULT_OVERLAP_TOKENS = 64


@dataclass(frozen=True)
class Chunk:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding(_ENCODING)


def _paragraphs(text: str) -> list[str]:
    """Split into paragraph-ish units on newlines; keeps table rows as their own units."""
    return [p.strip() for p in text.split("\n") if p.strip()]


def _pack(
    paragraphs: list[str], enc: tiktoken.Encoding, max_tokens: int, overlap_tokens: int
) -> list[str]:
    """Greedily pack paragraphs into token-bounded windows with token overlap between windows.

    A single paragraph longer than `max_tokens` (e.g. a huge table) is hard-split by tokens.
    """
    chunks: list[str] = []
    cur_ids: list[int] = []

    def flush() -> None:
        nonlocal cur_ids
        if cur_ids:
            chunks.append(enc.decode(cur_ids).strip())
            cur_ids = cur_ids[-overlap_tokens:] if overlap_tokens else []

    for para in paragraphs:
        ids = enc.encode(para + "\n")
        if len(ids) > max_tokens:
            flush()
            cur_ids = []
            for i in range(0, len(ids), max_tokens - overlap_tokens):
                window = ids[i : i + max_tokens]
                chunks.append(enc.decode(window).strip())
            continue
        if len(cur_ids) + len(ids) > max_tokens:
            flush()
        cur_ids += ids
    flush()
    return [c for c in chunks if c]


def chunk_filing(
    filing: Filing,
    sections: list[Section],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Turn parsed sections into embed-ready chunks with citation metadata."""
    enc = _encoder()
    base = {
        "ticker": filing.ticker,
        "company": filing.company,
        "cik": filing.cik,
        "form": filing.form,
        "fiscal_year": filing.fiscal_year,
        "accession": filing.accession,
        "source_url": filing.url,
    }
    out: list[Chunk] = []
    for section in sections:
        windows = _pack(_paragraphs(section.text), enc, max_tokens, overlap_tokens)
        for i, w in enumerate(windows):
            meta = {
                **base,
                "item": section.item,
                "section_title": section.title,
                "chunk_index": i,
                "n_tokens": len(enc.encode(w)),
                # stable, human-readable id: NVDA-2026-Item1A-3
                "chunk_id": f"{filing.ticker}-{filing.fiscal_year}-{section.item.replace(' ', '')}-{i}",
            }
            out.append(Chunk(text=w, metadata=meta))
    return out


def chunk_to_record(chunk: Chunk) -> dict[str, Any]:
    """Flatten to a single dict row (for LanceDB / pgvector upserts)."""
    return {"text": chunk.text, **chunk.metadata}


__all__ = ["Chunk", "chunk_filing", "chunk_to_record"]
