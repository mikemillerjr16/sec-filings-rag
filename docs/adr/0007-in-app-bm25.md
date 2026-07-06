# ADR 0007 — In-application BM25 (single hybrid code path on both backends)

**Status:** Accepted · **Date:** 2026-07-06

## Context

Hybrid retrieval needs a lexical arm alongside dense vectors. On Track 2 (Postgres + pgvector) the
tempting choice is Postgres full-text search; on Track 1 (LanceDB) there is no server to delegate
to. Using each backend's native lexical search would mean **two different BM25 implementations** to
build, tune, and reason about — and the RRF fusion above them would subtly differ per backend.

## Decision

Keep **BM25 in the application** (`bm25s`) for **both** backends. Only the *vector* store swaps
behind the `VectorStore` interface; the BM25 index, the RRF fusion, and the rerank step are the
exact same code regardless of backend.

## Consequences

- **One** hybrid code path to test and tune; the backend-abstraction story stays clean (the thing
  above the interface never forks).
- The BM25 index is a small artifact persisted alongside the vectors (local dir, or synced from S3
  on Track 1).
- We give up Postgres FTS features on Track 2 (e.g. server-side lexical filtering); acceptable,
  since ticker filtering is applied uniformly in-app and the corpus is small.
