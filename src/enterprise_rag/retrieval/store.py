"""Backend-agnostic vector store.

The whole app talks to the `VectorStore` protocol; only the concrete backend swaps between tracks:
LanceDB (embedded, S3-native) on Track 1 / local, pgvector (RDS) on Track 2. Keeping the interface
narrow is what lets one codebase run in both places — see docs/adr/0002.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from enterprise_rag.config import Settings, StoreBackend, get_settings

TABLE_NAME = "filings"
VECTOR_COLUMN = "vector"


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    text: str
    score: float  # higher = more similar (cosine similarity)
    metadata: dict[str, Any]


class VectorStore(Protocol):
    def write(self, records: list[dict[str, Any]]) -> None:
        """(Re)build the store from fully-formed records (each has `vector` + metadata)."""
        ...

    def search(
        self, query_vector: list[float], k: int = 10, where: str | None = None
    ) -> list[SearchHit]: ...

    def count(self) -> int: ...


class LanceDBStore:
    """LanceDB backend. `uri` is a local path for dev or `s3://bucket/prefix` on Lambda."""

    def __init__(self, uri: str, table_name: str = TABLE_NAME) -> None:
        self._uri = uri
        self._table_name = table_name

    def _connect(self) -> Any:
        import lancedb

        if "://" not in self._uri:  # local path — make sure the parent exists
            Path(self._uri).mkdir(parents=True, exist_ok=True)
        return lancedb.connect(self._uri)

    def write(self, records: list[dict[str, Any]]) -> None:
        if not records:
            raise ValueError("no records to write")
        db = self._connect()
        # Full rebuild keeps ingestion idempotent for our handful of filings.
        db.create_table(self._table_name, data=records, mode="overwrite")

    def _table(self) -> Any:
        return self._connect().open_table(self._table_name)

    def search(
        self, query_vector: list[float], k: int = 10, where: str | None = None
    ) -> list[SearchHit]:
        q = self._table().search(query_vector, vector_column_name=VECTOR_COLUMN).metric("cosine")
        if where:
            q = q.where(where)
        rows = q.limit(k).to_list()
        return [_row_to_hit(r) for r in rows]

    def count(self) -> int:
        return int(self._table().count_rows())


def _row_to_hit(row: dict[str, Any]) -> SearchHit:
    # LanceDB returns `_distance` (cosine distance in [0, 2]); convert to similarity.
    distance = float(row.pop("_distance", 0.0))
    row.pop(VECTOR_COLUMN, None)
    return SearchHit(
        chunk_id=str(row.get("chunk_id", "")),
        text=str(row.get("text", "")),
        score=1.0 - distance,
        metadata=row,
    )


def get_store(settings: Settings | None = None) -> VectorStore:
    s = settings or get_settings()
    if s.store_backend is StoreBackend.lancedb:
        return LanceDBStore(s.lancedb_uri)
    # pgvector backend lands with Track 2 (Phase 6); the interface is ready for it.
    raise NotImplementedError(f"store backend {s.store_backend!r} not implemented yet")
