# ADR 0006 — Reranker split: Cohere API (Track 1) vs local cross-encoder (Track 2)

**Status:** Accepted · **Date:** 2026-07-06

## Context

After hybrid retrieval fuses dense + lexical candidates, a cross-encoder rerank meaningfully
improves final ordering. The obvious implementation — a local `sentence-transformers` cross-encoder
— pulls in **torch**, which is hundreds of MB. On the Track-1 scale-to-zero Lambda that would bloat
the image and turn a ~10s cold start into something much worse, directly undermining the project's
cost/latency story.

## Decision

Make reranking pluggable (`RERANK_BACKEND = cohere | local | none`):

- **Track 1 (Lambda):** **Cohere Rerank API** (`rerank-v3.5`). A network call, no heavy deps — the
  image stays small and cold starts stay honest.
- **Local dev / Track 2 (ECS):** **local cross-encoder** (`ms-marco-MiniLM`), an optional
  dependency group (`rerank-local`) that is not installed by default.
- **Fallback:** a **Noop** reranker (keep fused order) when no key/model is available, so the
  pipeline degrades gracefully instead of crashing.

## Consequences

- The Lambda runtime never imports torch; the local/Track-2 path can rerank fully offline.
- One extra external dependency (Cohere) on the demo path — acceptable, and it has a free tier.
- Slight quality difference between tracks (different rerank models), which is fine for a demo and
  is exactly the sort of cost/latency-vs-quality trade the FinOps story is about.
