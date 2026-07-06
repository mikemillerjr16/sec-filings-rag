# Architecture Decision Records

Short records of *why* each non-obvious choice was made — the reasoning is part of the portfolio.
Each ADR lands with the phase that implements it.

Format: **Context → Decision → Consequences (incl. the trade-off we accepted)**.

| ADR | Decision | Status |
|-----|----------|--------|
| [0001](0001-two-track-cost-optimized-deployment.md) | Two-track deployment (serverless demo + on-demand ECS reference) | Accepted |
| 0002 | LanceDB (Track 1) vs pgvector (Track 2) behind one interface | Implemented (LanceDB); pgvector at Phase 6 |
| 0003 | Buffered responses on Lambda vs true SSE streaming on ECS | Implemented (Phase 2) |
| 0004 | SSM Parameter Store (Track 1) vs Secrets Manager (Track 2) | Planned (Phase 5) |
| 0005 | Shared-secret header + throttle vs WAF for the demo endpoint | Implemented guard (Phase 2); infra at Phase 5 |
| [0006](0006-reranker-split-cohere-vs-local.md) | Cohere Rerank API (Track 1) vs local cross-encoder (local/Track 2) | Accepted (Phase 3) |
| [0007](0007-in-app-bm25.md) | In-app BM25 on both backends (single hybrid code path) | Accepted (Phase 3) |
