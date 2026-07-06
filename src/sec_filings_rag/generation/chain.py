"""The RAG pipeline: retrieve -> format context -> LLM -> grounded, cited answer.

Retrieval and generation are wrapped in Langfuse observations so each request shows up as one trace
with a retriever span (which chunks) and a generation span (tokens, cost, latency).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from sec_filings_rag.config import Settings, get_settings
from sec_filings_rag.generation.prompts import (
    SYSTEM_PROMPT,
    USER_TEMPLATE,
    format_context,
    source_citation,
)
from sec_filings_rag.observability.tracing import flush, get_handler, get_langfuse
from sec_filings_rag.retrieval.retriever import DEFAULT_K, Retriever
from sec_filings_rag.retrieval.store import SearchHit


@dataclass
class Answer:
    text: str
    sources: list[dict[str, Any]]
    hits: list[SearchHit]


class RagPipeline:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._retriever = Retriever(self._settings)
        self._llm = ChatOpenAI(
            model=self._settings.llm_model,
            openai_api_key=self._settings.openai_api_key,
            temperature=0,
        )
        self._prompt = ChatPromptTemplate.from_messages(
            [("system", SYSTEM_PROMPT), ("human", USER_TEMPLATE)]
        )

    def _retrieve(self, question: str, k: int, where: str | None) -> list[SearchHit]:
        client = get_langfuse()
        if client is None:
            return self._retriever.retrieve(question, k=k, where=where)
        with client.start_as_current_observation(
            name="retrieve", as_type="retriever", input={"query": question, "where": where}
        ):
            hits = self._retriever.retrieve(question, k=k, where=where)
            client.update_current_span(
                output={"chunk_ids": [h.chunk_id for h in hits], "scores": [h.score for h in hits]}
            )
        return hits

    def _generate(self, question: str, hits: list[SearchHit]) -> str:
        chain = self._prompt | self._llm | StrOutputParser()
        handler = get_handler()
        config: RunnableConfig = {"callbacks": [handler]} if handler else {}
        return chain.invoke({"question": question, "context": format_context(hits)}, config=config)

    def answer(self, question: str, k: int = DEFAULT_K, where: str | None = None) -> Answer:
        client = get_langfuse()
        if client is None:
            hits = self._retrieve(question, k, where)
            return _build_answer(self._generate(question, hits), hits)

        with client.start_as_current_observation(
            name="rag_answer", as_type="span", input={"question": question, "k": k, "where": where}
        ):
            hits = self._retrieve(question, k, where)
            answer = _build_answer(self._generate(question, hits), hits)
            client.update_current_span(
                output={"answer": answer.text, "n_sources": len(answer.sources)}
            )
        flush()  # ensure the trace is sent (matters on Lambda)
        return answer

    def stream(
        self, question: str, k: int = DEFAULT_K, where: str | None = None
    ) -> Iterator[dict[str, Any]]:
        """Yield SSE-ready events: one 'sources' event, then 'token' deltas, then 'done'.

        This is the Track-2 (ECS) true-streaming path; Track-1 (Lambda) uses buffered `answer()`.
        """
        client = get_langfuse()
        span_cm = (
            client.start_as_current_observation(
                name="rag_answer_stream", as_type="span", input={"question": question, "k": k}
            )
            if client is not None
            else nullcontext()
        )
        with span_cm:
            hits = self._retrieve(question, k, where)
            yield {
                "type": "sources",
                "sources": [source_citation(i, h) for i, h in enumerate(hits, start=1)],
            }
            handler = get_handler()
            config: RunnableConfig = {"callbacks": [handler]} if handler else {}
            parts: list[str] = []
            for chunk in (self._prompt | self._llm).stream(
                {"question": question, "context": format_context(hits)}, config=config
            ):
                token = str(chunk.content or "")
                if token:
                    parts.append(token)
                    yield {"type": "token", "text": token}
            if client is not None:
                client.update_current_span(output={"answer": "".join(parts)})
        flush()
        yield {"type": "done"}


def _build_answer(text: str, hits: list[SearchHit]) -> Answer:
    sources = [source_citation(i, h) for i, h in enumerate(hits, start=1)]
    return Answer(text=text, sources=sources, hits=hits)


_PIPELINE: RagPipeline | None = None


def get_pipeline() -> RagPipeline:
    """Lazily-built singleton (reused across warm Lambda invocations)."""
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = RagPipeline()
    return _PIPELINE
