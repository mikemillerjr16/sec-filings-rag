# Architecture

This project is deliberately built as **two deployment tracks** that share one codebase. The split
demonstrates the AWS Well-Architected **Cost Optimization** pillar in practice: a production-grade
reference architecture that you can stand up on demand, plus an always-on public demo that runs at
effectively zero cost.

## Shared application

```
Ingestion (offline, run once):
  SEC EDGAR -> parse 10-K (structure-aware) -> clean -> chunk -> embed
           -> build LanceDB index (vectors + metadata) + in-app BM25 index

Query time:
  question -> hybrid retrieve (BM25 + vector, RRF fusion) -> rerank
           -> LCEL prompt -> LLM -> grounded answer + citations
           -> Langfuse trace (retrieval spans, tokens, cost, latency)
```

A single `STORE_BACKEND` interface (`lancedb | pgvector`) means only the vector store swaps between
tracks. **BM25 is in-app on both backends**, so the hybrid-fusion logic is one code path, not two.

## Track 1 — Serverless demo (always-on, ~$0/mo)

```
User -> Streamlit UI -> Lambda Function URL (FastAPI via Mangum, buffered response)
                          |-> S3: LanceDB index + BM25 index
                          |-> OpenAI (embeddings + gpt-4o-mini)
                          |-> Cohere Rerank API
                          |-> Langfuse Cloud (free tier)
                          |-> SSM Parameter Store (secrets, free tier)
```

- **Scales to zero** — no idle compute. No NAT Gateway, no ALB, no RDS, no DynamoDB.
- **Cold start** is real: the Streamlit host waking + Lambda cold start can total ~20–30s on the
  first request. The UI says so plainly — that honesty *is* the cost-optimization story.
- **Endpoint is guarded** by a shared-secret header (sent by the UI) plus light per-IP throttling,
  because a public Function URL is an unauthenticated proxy to a metered LLM.
- **Buffered responses** — Lambda Function URL streaming via Mangum is unreliable, so streaming is
  intentionally a Track-2 capability.

## Track 2 — Production reference (on-demand, $0 when destroyed)

```
ALB -> ECS Fargate (FastAPI, true SSE streaming) -> RDS Postgres + pgvector
         |-> OpenAI | Langfuse | CloudWatch (logs/metrics) | Secrets Manager (rotation/audit)
      VPC with public/private subnets, least-privilege IAM
```

- The "enterprise" answer: managed Postgres with pgvector, a load balancer (WAF/rate-limiting
  available), Secrets Manager with rotation, CloudWatch observability, true token streaming.
- **Validated once** (`terraform apply` → verify a live answer via the ALB → `terraform destroy`),
  then it lives here as an IaC artifact. It is not a maintained, always-on environment — that would
  reintroduce the ~$85–100/mo cost this project is explicitly avoiding.

## Cost guardrails

- OpenAI hard billing cap (dashboard).
- AWS Budgets alarm at $5.
- `.gitignore` + `.dockerignore` keep large artifacts (indexes, filings, venv) out of git and out
  of the image.

See [`adr/`](adr/) for the decision records behind each of these choices.
