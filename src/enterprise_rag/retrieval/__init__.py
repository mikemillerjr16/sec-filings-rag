"""Retrieval: backend-agnostic vector store (lancedb | pgvector) + shared in-app BM25 + RRF
fusion + reranker. Only the vector store swaps behind the interface; BM25/fusion is one code
path across both backends (Phase 2-3).
"""
