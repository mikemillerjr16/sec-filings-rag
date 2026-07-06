"""Offline API tests — wiring, input validation, and auth logic without hitting the LLM."""

from fastapi.testclient import TestClient

from enterprise_rag.api.app import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_bad_ticker_rejected_before_pipeline() -> None:
    # A filter-injection attempt must be rejected with 400 (no LLM/store call happens).
    r = client.post("/query", json={"question": "hello there", "ticker": "NVDA' OR 1=1--"})
    assert r.status_code == 400


def test_question_too_short_is_422() -> None:
    r = client.post("/query", json={"question": "hi"})
    assert r.status_code == 422  # pydantic validation (min_length)
