"""Central, environment-driven configuration.

One `Settings` object is the single source of truth for the whole app. The same code runs on
Track 1 (Lambda + LanceDB-on-S3) and Track 2 (ECS + pgvector) — only these env values change,
which is the point of the `STORE_BACKEND` / `RERANK_BACKEND` switches.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRET = "change-me-in-parameter-store"  # the .env.example default => auth off


class StoreBackend(StrEnum):
    lancedb = "lancedb"
    pgvector = "pgvector"


class RerankBackend(StrEnum):
    cohere = "cohere"
    local = "local"
    none = "none"


class Settings(BaseSettings):
    """Loaded from environment / `.env`. Secrets come from Parameter Store or Secrets Manager
    in AWS; nothing sensitive is ever committed."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM / embeddings ---
    openai_api_key: str = Field(default="", description="OpenAI API key")
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    # --- Reranking ---
    cohere_api_key: str = ""
    rerank_backend: RerankBackend = RerankBackend.cohere

    # --- Observability (Langfuse) ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # --- Vector store ---
    store_backend: StoreBackend = StoreBackend.lancedb
    lancedb_uri: str = "./data.nosync/lancedb"
    pgvector_dsn: str = "postgresql://rag:rag@localhost:5432/rag"

    # --- SEC EDGAR ---
    sec_user_agent: str = "enterprise-rag-portfolio contact@example.com"

    # --- Track 1 endpoint auth ---
    api_shared_secret: str = ""

    # --- Local data ---
    filings_dir: str = "./filings.nosync"

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def auth_enabled(self) -> bool:
        """True once a real shared secret is set (not empty, not the .env.example placeholder)."""
        return bool(self.api_shared_secret) and self.api_shared_secret != PLACEHOLDER_SECRET


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so config is parsed once per process (incl. warm Lambda invocations)."""
    return Settings()
