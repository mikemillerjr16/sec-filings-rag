"""Streamlit chat UI for the Enterprise RAG API.

Talks to the FastAPI backend over HTTP (locally, or the Lambda Function URL in the hosted demo),
streaming tokens as they arrive and rendering inline source citations. The cold-start banner is
deliberately honest: on the serverless demo, the UI host and the Lambda both scale to zero, so the
first request pays two wake-ups.
"""

from __future__ import annotations

import json
import os

import httpx
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")
API_SHARED_SECRET = os.environ.get("API_SHARED_SECRET", "")
COMPANIES = {
    "All companies": None,
    "NVIDIA (NVDA)": "NVDA",
    "AMD": "AMD",
    "Microsoft (MSFT)": "MSFT",
}

st.set_page_config(page_title="Enterprise RAG — SEC 10-K Q&A", page_icon="📊", layout="centered")


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if API_SHARED_SECRET:
        h["X-API-Key"] = API_SHARED_SECRET
    return h


def stream_answer(question: str, ticker: str | None, k: int):
    """Generator yielding token text; stashes the sources list in session_state."""
    payload = {"question": question, "k": k}
    if ticker:
        payload["ticker"] = ticker
    with httpx.stream(
        "POST", f"{API_URL}/query/stream", json=payload, headers=_headers(), timeout=120.0
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event["type"] == "sources":
                st.session_state["last_sources"] = event["sources"]
            elif event["type"] == "token":
                yield event["text"]


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander(f"📎 {len(sources)} sources"):
        for s in sources:
            label = f"**[{s['n']}] {s['ticker']} {s['item']}** · FY{s['fiscal_year']} · score {s['score']}"
            st.markdown(f"{label}  \n[{s['section_title'][:70]}]({s['source_url']})")


# --- Sidebar ---
with st.sidebar:
    st.header("Ask the filings")
    company = st.selectbox("Company filter", list(COMPANIES.keys()))
    k = st.slider("Sources to retrieve (k)", 3, 15, 8)
    st.divider()
    st.caption(
        "Corpus: latest 10-K filings for NVDA, AMD, MSFT. Answers are grounded in the filings "
        "with inline citations; the assistant refuses when the filings don't contain the answer."
    )
    st.caption(f"API: `{API_URL}`")

# --- Header + honest cold-start banner ---
st.title("📊 Enterprise RAG over SEC 10-K Filings")
st.info(
    "⏳ **First request may take ~20–30s.** The demo UI and the API both scale to zero to run at "
    "~$0/month — so the first call pays a cold start. Subsequent questions are fast.",
    icon="💸",
)

if "messages" not in st.session_state:
    st.session_state["messages"] = []

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            render_sources(msg["sources"])

if prompt := st.chat_input("e.g. Compare NVIDIA's and AMD's supply-chain risks"):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        st.session_state["last_sources"] = []
        try:
            answer = st.write_stream(stream_answer(prompt, COMPANIES[company], k))
        except httpx.HTTPError as e:
            answer = f"⚠️ Could not reach the API at `{API_URL}` ({e}). Is it running?"
            st.error(answer)
        sources = st.session_state.get("last_sources", [])
        render_sources(sources)

    st.session_state["messages"].append(
        {"role": "assistant", "content": answer, "sources": sources}
    )
