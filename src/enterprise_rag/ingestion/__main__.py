"""`python -m enterprise_rag.ingestion [TICKER ...]` — build the indexes from SEC 10-Ks."""

from __future__ import annotations

import argparse
import logging

from enterprise_rag.ingestion.pipeline import DEFAULT_TICKERS, ingest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tickers",
        nargs="*",
        help=f"ticker symbols to ingest (default: {' '.join(DEFAULT_TICKERS)})",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    report = ingest(args.tickers or None)
    print(f"\n{report}")


if __name__ == "__main__":
    main()
