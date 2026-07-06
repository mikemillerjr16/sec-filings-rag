# Enterprise RAG — developer tasks.
#
# NOTE: this repo lives inside iCloud Drive, so we keep the virtualenv OUTSIDE the synced tree.
# UV_PROJECT_ENVIRONMENT points uv at ~/.venvs/enterprise-rag; all `uv` calls inherit it.
export UV_PROJECT_ENVIRONMENT := $(HOME)/.venvs/enterprise-rag
# Avoid uv's "VIRTUAL_ENV does not match" noise when a shell venv (e.g. pyenv) is active.
unexport VIRTUAL_ENV

.DEFAULT_GOAL := help
.PHONY: help install sync config lint format typecheck test check \
        ingest api ui eval up down clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install sync:  ## Create the venv (outside iCloud) and install all deps + dev group
	uv sync --all-groups

config:  ## Print resolved (non-secret) configuration
	uv run sec-filings-rag config

lint:  ## Ruff lint
	uv run ruff check .

format:  ## Ruff format
	uv run ruff format .

typecheck:  ## mypy
	uv run mypy

test:  ## Run the test suite
	uv run pytest

check: lint typecheck test  ## Lint + typecheck + test (what CI runs)

# --- Phase 1+ targets (wired up as each phase lands) ---
ingest:  ## Fetch + parse + chunk + embed SEC 10-Ks into the vector store (Phase 1)
	uv run python -m sec_filings_rag.ingestion $(ARGS)

api:  ## Run the FastAPI app locally with reload (Phase 2)
	uv run uvicorn sec_filings_rag.api.app:app --reload --port 8000

ui:  ## Run the Streamlit chat UI (Phase 2)
	uv run streamlit run ui/streamlit_app.py

eval:  ## Run the adversarial RAGAS evaluation (Phase 4)
	uv run python -m sec_filings_rag.evaluation $(ARGS)

# --- Local infra (Postgres/pgvector + Langfuse) ---
up:  ## Start local Postgres+pgvector and self-hosted Langfuse
	docker compose up -d

down:  ## Stop local infra
	docker compose down

clean:  ## Remove caches (not the venv, not data)
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
