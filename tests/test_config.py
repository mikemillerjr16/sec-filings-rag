"""Smoke tests for configuration — proves the package imports and settings resolve."""

from enterprise_rag import __version__
from enterprise_rag.config import RerankBackend, Settings, StoreBackend, get_settings


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_defaults() -> None:
    s = Settings(_env_file=None)  # ignore any local .env for a deterministic test
    assert s.store_backend is StoreBackend.lancedb
    assert s.rerank_backend is RerankBackend.cohere
    assert s.llm_model == "gpt-4o-mini"
    assert s.langfuse_enabled is False  # no keys by default


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
