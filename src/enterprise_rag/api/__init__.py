"""API: FastAPI app exposing /query (SSE on ECS, buffered on Lambda) and /health. The Lambda
Function URL is guarded by a shared-secret header + per-IP throttle (Phase 2 / Phase 5).
"""
