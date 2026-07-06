"""Ingestion: SEC EDGAR fetch -> 10-K parse/clean -> chunk -> embed -> build index.

This is where retrieval quality is won or lost (10-K HTML tables are messy). Implemented in
Phase 1 against real filings, not synthetic samples.
"""
