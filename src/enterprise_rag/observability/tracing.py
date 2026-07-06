"""Langfuse tracing wiring.

Langfuse Cloud (free tier) backs the hosted demo; a self-hosted instance backs local dev. Both are
driven purely by env, so nothing here changes between them. If keys are absent, tracing is a no-op
so the app still runs (e.g. in unit tests).
"""

from __future__ import annotations

from functools import lru_cache

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from enterprise_rag.config import get_settings


@lru_cache
def get_langfuse() -> Langfuse | None:
    """Process-wide Langfuse client, or None when not configured."""
    s = get_settings()
    if not s.langfuse_enabled:
        return None
    return Langfuse(
        public_key=s.langfuse_public_key,
        secret_key=s.langfuse_secret_key,
        host=s.langfuse_host,
    )


def get_handler() -> CallbackHandler | None:
    """LangChain callback handler that nests LLM calls under the current trace."""
    return CallbackHandler() if get_langfuse() is not None else None


def flush() -> None:
    """Flush buffered traces — important on Lambda before the invocation returns."""
    client = get_langfuse()
    if client is not None:
        client.flush()
