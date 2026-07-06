"""Prompt templates + context formatting for grounded, cited answers.

The system prompt enforces the two behaviors that make a RAG demo credible to a technical reviewer:
strict grounding (refuse when the context doesn't support an answer) and inline citations that map
back to specific filing sections.
"""

from __future__ import annotations

from sec_filings_rag.retrieval.store import SearchHit

SYSTEM_PROMPT = """You are a precise financial-analysis assistant answering questions about \
companies' SEC 10-K filings.

Rules you must follow:
1. Answer ONLY using the provided context blocks. Do not use outside knowledge.
2. If the context does not contain enough information to answer, say exactly what is missing and \
state that it is not found in the provided filings. Never guess or fabricate figures.
3. Support every factual claim with inline citations using the bracketed source numbers, e.g. [1] \
or [2][3], matching the numbered context blocks.
4. Quote financial figures exactly as they appear (including units like "$ in millions").
5. Be concise and specific. When comparing companies, attribute each fact to its filing."""

USER_TEMPLATE = """Question: {question}

Context — each block is a citable source labeled with its number and provenance:
{context}

Answer the question using only the context above, with inline [n] citations."""


def format_context(hits: list[SearchHit]) -> str:
    """Render retrieved chunks as numbered, provenance-labeled blocks the model can cite."""
    blocks: list[str] = []
    for i, h in enumerate(hits, start=1):
        m = h.metadata
        header = (
            f"[{i}] {m.get('ticker', '?')} {m.get('form', '10-K')} "
            f"FY{m.get('fiscal_year', '?')} — {m.get('item', '')} "
            f"{m.get('section_title', '')}".strip()
        )
        blocks.append(f"{header}\n{h.text}")
    return "\n\n".join(blocks)


def source_citation(index: int, hit: SearchHit) -> dict[str, object]:
    """A structured citation for the API/UI to render alongside the answer."""
    m = hit.metadata
    return {
        "n": index,
        "chunk_id": hit.chunk_id,
        "ticker": m.get("ticker"),
        "fiscal_year": m.get("fiscal_year"),
        "item": m.get("item"),
        "section_title": m.get("section_title"),
        "source_url": m.get("source_url"),
        "score": round(hit.score, 4),
    }
