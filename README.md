# SEC Filings RAG

> Ask natural-language questions about public companies' annual reports and get grounded, **cited**
> answers — built as a production-shaped, **observable**, and deliberately **cost-optimized** RAG
> system. A Solutions-Architect + AI-Engineering portfolio project.

<!-- Badges (CI, license) land in Phase 7. Live demo URL lands in Phase 5. -->

---

## Why this project is different: designed for production, run at ~$0

Most portfolio RAG demos can't say anything credible about cost. This one is architected as **two
tracks**, and the split *is* the point — it's a working demonstration of the AWS Well-Architected
**Cost Optimization** pillar, not an afterthought:

| Track | What it is | Runs at | Purpose |
|-------|-----------|--------|---------|
| **1 — Serverless demo** | AWS Lambda (scale-to-zero) + LanceDB-on-S3 + SSM Parameter Store | **~$0/mo** | The always-on public demo you can click |
| **2 — Production reference** | Terraform: VPC, RDS pgvector, ECS Fargate, ALB, Secrets Manager | **$0 when destroyed** | The "real" enterprise architecture, deployed on demand |

The same application code runs on both, behind a `STORE_BACKEND` interface — only the vector store
and a few env values change. Track 2 is **validated once (`apply` → verify → `destroy`)** and then
lives in this repo as an Infrastructure-as-Code artifact you can read and I can walk through in an
interview. Deliberately avoided always-on cost sinks: NAT Gateway (~$32/mo), ALB (~$16/mo), 24/7
RDS/Fargate, and per-secret Secrets Manager charges on the demo path. Hard guardrails: an OpenAI
billing cap and an AWS Budgets alarm.

> **Trade-offs owned on purpose** (see [`docs/adr/`](docs/adr/)): the serverless demo returns a
> **buffered** answer (Lambda) while the ECS track does **true SSE token streaming**; reranking
> uses the **Cohere API** on Lambda (no heavy `torch` in the image) and a local cross-encoder only
> for local/Track 2; the demo endpoint is guarded by a **shared-secret header + throttle** rather
> than paying for a WAF.

## What it does

- Ingests real **SEC 10-K** filings from EDGAR, with structure-aware parsing and chunking.
- **Hybrid retrieval**: in-app BM25 + vector search fused with RRF, then a reranker.
- Grounded generation with **inline citations**; refuses when the context doesn't support an answer.
- First-class **observability** (Langfuse): every trace, token count, and cost is captured.
- An **honest, adversarial evaluation** (RAGAS): refusal, cross-filing, and table-dependent
  questions — with an explicit note that RAGAS uses a noisy LLM judge.

## Architecture

<!-- Diagram image lands in Phase 6/7. Text version below and in docs/architecture.md. -->

```
Ingestion (offline): SEC EDGAR -> parse 10-K -> clean -> chunk -> embed -> build LanceDB + BM25

Track 1  User -> Streamlit -> Lambda Function URL (FastAPI/Mangum, buffered)
                                 |-> S3: LanceDB index (vectors + metadata) + BM25
                                 |-> OpenAI (embeddings + gpt-4o-mini) | Cohere rerank
                                 |-> Langfuse Cloud | SSM Parameter Store

Track 2  ALB -> ECS Fargate (FastAPI, SSE) -> RDS Postgres + pgvector
                                 |-> OpenAI | Langfuse | CloudWatch | Secrets Manager
```

See [`docs/architecture.md`](docs/architecture.md) for the full write-up and the per-track
Well-Architected reasoning.

## Tech stack

Python 3.13 · [uv](https://docs.astral.sh/uv/) · LangChain · OpenAI · LanceDB / pgvector ·
FastAPI · Streamlit · Langfuse · RAGAS · Cohere Rerank · Terraform · AWS (Lambda, S3, ECS,
RDS, ALB)

## Quickstart (local)

```bash
make install        # create the venv (kept outside iCloud) + install deps
cp .env.example .env && $EDITOR .env   # add your OpenAI key, etc.
make check          # lint + typecheck + tests
# Phase 1+ :
make up             # local Postgres/pgvector + Langfuse (needs Docker)
make ingest         # pull + index a few 10-Ks
make api            # FastAPI on :8000
make ui             # Streamlit chat on :8501
```

## Evaluation results

_Landing in Phase 4 — a table comparing baseline vs hybrid+rerank on the adversarial golden set,
with the LLM-judge caveat stated plainly._

## Project status

Built in phases with a clean, reviewable git history (branch + PR per phase):

- [x] **Phase 0** — Foundations & scaffolding
- [x] **Phase 1** — Ingestion pipeline (the retrieval-quality battle)
- [x] **Phase 2** — Baseline RAG + API + UI + Langfuse
- [ ] **Phase 3** — Advanced retrieval (hybrid + rerank)
- [ ] **Phase 4** — Adversarial evaluation (RAGAS)
- [ ] **Phase 5** — Track 1 serverless deploy
- [ ] **Phase 6** — Track 2 production IaC artifact
- [ ] **Phase 7** — Portfolio polish (CI, diagram, demo)

## License

MIT (see `LICENSE`, added in Phase 7).
