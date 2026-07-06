"""Console entry point. Subcommands are wired up as each phase lands (ingest, eval, ...)."""

from __future__ import annotations

import argparse

from sec_filings_rag import __version__
from sec_filings_rag.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="sec-filings-rag", description=__doc__)
    parser.add_argument("--version", action="version", version=f"sec-filings-rag {__version__}")
    parser.add_argument(
        "config",
        nargs="?",
        help="print the resolved (non-secret) configuration and exit",
        choices=["config"],
    )
    args = parser.parse_args()

    if args.config == "config":
        s = get_settings()
        print(f"store_backend   = {s.store_backend}")
        print(f"rerank_backend  = {s.rerank_backend}")
        print(f"llm_model       = {s.llm_model}")
        print(f"embedding_model = {s.embedding_model}")
        print(f"langfuse        = {'enabled' if s.langfuse_enabled else 'disabled'}")
        print(f"lancedb_uri     = {s.lancedb_uri}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
