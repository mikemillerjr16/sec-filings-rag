"""OpenAI embeddings via LangChain.

We use LangChain where it earns its place (embeddings + the LCEL generation chain) and native
libraries where control matters (LanceDB indexing, in-app BM25). `text-embedding-3-small` is
1536-dim and cheap: embedding a few full 10-Ks costs well under $0.10.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from enterprise_rag.config import get_settings

EMBED_DIM = 1536  # text-embedding-3-small


@lru_cache
def get_embedder() -> OpenAIEmbeddings:
    s = get_settings()
    if not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set — add it to .env")
    return OpenAIEmbeddings(model=s.embedding_model, openai_api_key=s.openai_api_key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed document chunks (LangChain batches internally)."""
    return get_embedder().embed_documents(texts)


def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    return get_embedder().embed_query(text)
