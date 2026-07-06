# ADR 0001 — Two-track cost-optimized deployment

**Status:** Accepted · **Date:** 2026-07-06

## Context

This is a portfolio project that must (a) showcase real Solutions-Architect depth on AWS and (b)
survive for months/years without meaningful cost. A single always-on "production" stack (VPC + NAT
Gateway + ALB + ECS Fargate + RDS) costs roughly **$85–100/month sitting idle** — about half of
that is the NAT Gateway (~$32) and ALB (~$16) doing nothing. That is unacceptable for a demo that
mostly receives zero traffic. But collapsing everything to the cheapest possible thing would throw
away the architecture story that makes the project worth showing.

## Decision

Build **two tracks that share one application codebase**:

1. **Track 1 — serverless demo (always-on, ~$0/mo):** AWS Lambda (scale-to-zero) behind a Function
   URL, LanceDB index on S3, secrets in SSM Parameter Store, Langfuse Cloud free tier. This is the
   public, clickable demo.
2. **Track 2 — production reference (on-demand):** full Terraform for VPC, RDS + pgvector, ECS
   Fargate, ALB, Secrets Manager, CloudWatch. Deployed for a demo/interview, then `terraform
   destroy`. It lives in the repo as an IaC artifact — code that exists, not an environment that is
   maintained.

A `STORE_BACKEND` interface keeps the two tracks on the same code; only the vector store and a few
env values differ.

## Consequences

**Positive**
- Idle cost drops from ~$90/mo to ~$0–1/mo while keeping the full architecture readable in-repo.
- The split itself becomes a talking point: a concrete Well-Architected Cost-Optimization story
  ("designed for production, run cost-optimized") that most portfolios can't tell.

**Trade-offs accepted (owned, not hidden)**
- Track 1 returns **buffered** responses (Lambda streaming is unreliable); true token streaming is
  a Track-2 capability. See ADR 0003.
- Track 1 has a **cold start** (UI + Lambda) of ~20–30s on first hit; the UI states this plainly.
- Track 2 is not continuously live, so the demo URL points at Track 1, not the "real" architecture.
- Maintaining one codebase across two runtimes (Lambda container + ECS) requires a deliberate
  per-platform entrypoint; complexity is contained in the Dockerfile.
